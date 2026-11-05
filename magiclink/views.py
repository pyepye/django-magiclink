import logging

from django import forms
from django.conf import settings as django_settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.signing import BadSignature
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from . import ratelimit, settings
from .adapter import get_adapter
from .forms import (
    LoginForm,
    SignupForm,
    SignupFormEmailOnly,
    SignupFormFull,
    SignupFormWithUsername,
)
from .helpers import create_magiclink, get_or_create_user
from .models import (
    MagicLink,
    MagicLinkError,
    MagicLinkUnsubscribe,
    unsign_unsubscribe_email,
)
from .signals import login_failed, spam_detected
from .utils import get_safe_redirect_url, get_url_path

User = get_user_model()
log = logging.getLogger(__name__)

FORM_SPAM = "The form failed the anti spam checks"
TOO_MANY_REQUESTS = "Too many requests, please try again later"

SIGNUP_FORMS = {
    form.__name__: form
    for form in (
        SignupForm,
        SignupFormEmailOnly,
        SignupFormWithUsername,
        SignupFormFull,
    )
}


class SettingTemplateView(TemplateView):
    template_setting = ""

    def get_template_names(self) -> list[str]:
        return [self.template_name or getattr(settings, self.template_setting)]


class SpamCheckedView(SettingTemplateView):
    form_class: type[forms.Form] | None = None
    form_setting_key = ""

    def custom_form_class(self):
        if self.form_class:
            return self.form_class
        path = settings.FORMS.get(self.form_setting_key)
        return import_string(path) if path else None

    def spam_response(self, context, form_key, form, reason) -> HttpResponse:
        spam_detected.send(
            sender=self.__class__, request=self.request, form=form, reason=reason
        )
        if settings.ANTISPAM_QUIET_REJECT:
            return HttpResponseRedirect(get_url_path(settings.LOGIN_SENT_REDIRECT))
        context[form_key] = form
        return self.render_to_response(context)

    def rate_limited_response(self, context, form_key, form) -> HttpResponse:
        form.errors.clear()
        form.add_error("email", TOO_MANY_REQUESTS)
        return self.spam_response(context, form_key, form, TOO_MANY_REQUESTS)


@method_decorator(csrf_protect, name="dispatch")
class Login(SpamCheckedView):
    template_setting = "LOGIN_TEMPLATE_NAME"
    form_setting_key = "login"

    def get_form_class(self):
        return self.custom_form_class() or LoginForm

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["login_form"] = self.get_form_class()()
        context["require_signup"] = settings.REQUIRE_SIGNUP
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        context["require_signup"] = settings.REQUIRE_SIGNUP
        form = self.get_form_class()(request.POST)
        if ratelimit.hit("request", request, request.POST.get("email", "")):
            return self.rate_limited_response(context, "login_form", form)

        if not form.is_valid():
            if form.is_spam():
                return self.spam_response(context, "login_form", form, FORM_SPAM)
            context["login_form"] = form
            return self.render_to_response(context)

        email = form.cleaned_data["email"]
        reason = get_adapter().check_request(request, email, form)
        if reason:
            form.add_error("email", reason)
            return self.spam_response(context, "login_form", form, reason)

        if ratelimit.hit("request_site", request):
            return self.rate_limited_response(context, "login_form", form)

        if not settings.REQUIRE_SIGNUP and form.send_email:
            get_or_create_user(email)

        redirect_url = self.login_redirect_url(request.GET.get("next", ""))
        try:
            magiclink = create_magiclink(email, request, redirect_url=redirect_url)
        except MagicLinkError as e:
            if settings.PREVENT_ENUMERATION or self.has_live_magiclink(email):
                return HttpResponseRedirect(get_url_path(settings.LOGIN_SENT_REDIRECT))
            form.add_error("email", str(e))
            context["login_form"] = form
            return self.render_to_response(context)

        if form.send_email:
            magiclink.send(request)

        sent_url = get_url_path(settings.LOGIN_SENT_REDIRECT)
        response = HttpResponseRedirect(sent_url)
        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f"magiclink{magiclink.pk}"
            response.set_cookie(
                cookie_name,
                magiclink.cookie_value,
                httponly=True,
                secure=request.is_secure(),
                samesite="Lax",
            )
            log.info(f"Cookie {cookie_name} set for {email}")
        return response

    def login_redirect_url(self, next_url) -> str:
        return get_safe_redirect_url(self.request, next_url)

    def has_live_magiclink(self, email: str) -> bool:
        return MagicLink.objects.filter(
            email=email, disabled=False, expiry__gt=timezone.now()
        ).exists()


class LoginSent(SettingTemplateView):
    template_setting = "LOGIN_SENT_TEMPLATE_NAME"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["prevent_enumeration"] = settings.PREVENT_ENUMERATION
        return context


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class LoginVerify(SettingTemplateView):
    template_setting = "LOGIN_FAILED_TEMPLATE_NAME"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response.setdefault("Referrer-Policy", "no-referrer")
        return response

    def get(self, request, *args, **kwargs):
        if settings.LOGIN_CONFIRM:
            return self.confirm_response(**kwargs)
        return self.verify(request, **kwargs)

    def post(self, request, *args, **kwargs):
        if not settings.LOGIN_CONFIRM:
            return self.http_method_not_allowed(request, *args, **kwargs)
        return self.verify(request, **kwargs)

    def confirm_response(self, **kwargs) -> HttpResponse:
        response = self.response_class(
            request=self.request,
            template=[settings.LOGIN_CONFIRM_TEMPLATE_NAME],
            context=self.get_context_data(**kwargs),
        )
        # no-referrer makes browsers send "Origin: null" with the form, which
        # fails Django's CSRF check. strict-origin still keeps the token private.
        response["Referrer-Policy"] = "strict-origin"
        return response

    def verify(self, request, **kwargs) -> HttpResponse:
        token = request.GET.get("token")
        email = request.GET.get("email")
        if ratelimit.is_limited("verify_failed", request, email or ""):
            login_failed.send(
                sender=self.__class__,
                request=request,
                magiclink=None,
                reason=TOO_MANY_REQUESTS,
            )
            return self.failed_response(TOO_MANY_REQUESTS, **kwargs)

        user = authenticate(request, token=token, email=email)
        if not user:
            ratelimit.hit("verify_failed", request, email or "")
            return self.failed_response(**kwargs)

        login(request, user)
        log.info(f"Login successful for {email}")

        response = self.login_complete_action()
        if settings.REQUIRE_SAME_BROWSER:
            magiclink = MagicLink.objects.get(token=token)
            cookie_name = f"magiclink{magiclink.pk}"
            response.delete_cookie(cookie_name)
        return response

    def failed_response(self, login_error=None, **kwargs) -> HttpResponse:
        if settings.LOGIN_FAILED_REDIRECT:
            redirect_url = get_url_path(settings.LOGIN_FAILED_REDIRECT)
            return HttpResponseRedirect(redirect_url)

        if not settings.LOGIN_FAILED_TEMPLATE_NAME:
            raise Http404()

        context = self.get_context_data(**kwargs)
        # The below settings are left in for backward compatibility
        context["ONE_TOKEN_PER_USER"] = settings.ONE_TOKEN_PER_USER
        context["REQUIRE_SAME_BROWSER"] = settings.REQUIRE_SAME_BROWSER
        context["REQUIRE_SAME_IP"] = settings.REQUIRE_SAME_IP
        context["ALLOW_SUPERUSER_LOGIN"] = settings.ALLOW_SUPERUSER_LOGIN
        context["ALLOW_STAFF_LOGIN"] = settings.ALLOW_STAFF_LOGIN
        context["login_error"] = login_error or self.link_error()
        return self.render_to_response(context)

    def link_error(self) -> str:
        token = self.request.GET.get("token")
        email = self.request.GET.get("email", "")
        try:
            magiclink = MagicLink.objects.get(token=token)
        except MagicLink.DoesNotExist:
            return "A magic link with that token could not be found"

        try:
            magiclink.validate(self.request, email)
        except MagicLinkError as error:
            return str(error)
        return ""

    def login_complete_action(self) -> HttpResponse:
        token = self.request.GET.get("token")
        magiclink = MagicLink.objects.get(token=token)
        return HttpResponseRedirect(magiclink.redirect_url)


@method_decorator(csrf_protect, name="dispatch")
class Signup(SpamCheckedView):
    template_setting = "SIGNUP_TEMPLATE_NAME"
    form_setting_key = "signup"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        custom_form_class = self.custom_form_class()
        for name, form_class in SIGNUP_FORMS.items():
            context[name] = (custom_form_class or form_class)()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        form_name = request.POST.get("form_name")
        # A custom form handles every POST, so a bot can not name a default form
        # to avoid the fields the custom form adds.
        custom_form_class = self.custom_form_class()
        form_class = custom_form_class or SIGNUP_FORMS.get(form_name)
        if form_class is None:
            return HttpResponseRedirect(self.request.path)

        form = form_class(request.POST)
        if custom_form_class:
            form_name = "SignupForm"
            context.update(dict.fromkeys(SIGNUP_FORMS, form))

        if ratelimit.hit("request", request, request.POST.get("email", "")):
            return self.rate_limited_response(context, form_name, form)

        if not form.is_valid():
            if form.is_spam():
                return self.spam_response(context, form_name, form, FORM_SPAM)
            context[form_name] = form
            return self.render_to_response(context)

        email = form.cleaned_data["email"]
        reason = get_adapter().check_request(request, email, form)
        if reason:
            form.add_error("email", reason)
            return self.spam_response(context, form_name, form, reason)

        if ratelimit.hit("request_site", request):
            return self.rate_limited_response(context, form_name, form)

        full_name = form.cleaned_data.get("name", "")
        try:
            first_name, last_name = full_name.split(" ", 1)
        except ValueError:
            first_name = full_name
            last_name = ""

        if form.create_user:
            get_or_create_user(
                email=email,
                username=form.cleaned_data.get("username", ""),
                first_name=first_name,
                last_name=last_name,
            )
        next_url = get_safe_redirect_url(request, request.GET.get("next", ""))
        if not next_url:
            next_url = get_url_path(settings.SIGNUP_LOGIN_REDIRECT)
        try:
            magiclink = create_magiclink(email, request, redirect_url=next_url)
        except MagicLinkError:
            if not settings.PREVENT_ENUMERATION:
                raise
            return HttpResponseRedirect(get_url_path(settings.LOGIN_SENT_REDIRECT))

        if form.send_email:
            magiclink.send(request)

        sent_url = get_url_path(settings.LOGIN_SENT_REDIRECT)
        response = HttpResponseRedirect(sent_url)
        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f"magiclink{magiclink.pk}"
            response.set_cookie(
                cookie_name,
                magiclink.cookie_value,
                httponly=True,
                secure=request.is_secure(),
                samesite="Lax",
            )
            log.info(f"Cookie {cookie_name} set for {email}")
        return response


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class Unsubscribe(SettingTemplateView):
    template_setting = "UNSUBSCRIBE_TEMPLATE_NAME"

    def get(self, request, *args, **kwargs):
        return self.unsubscribe_response(unsubscribe=False, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.unsubscribe_response(unsubscribe=True, **kwargs)

    def unsubscribe_response(self, unsubscribe: bool, **kwargs) -> HttpResponse:
        context = self.get_context_data(**kwargs)
        try:
            email = unsign_unsubscribe_email(self.request.GET.get("email", ""))
        except BadSignature:
            context["invalid_link"] = True
            return self.render_to_response(context, status=400)

        context["email"] = email
        if unsubscribe:
            if not MagicLinkUnsubscribe.objects.filter(email=email).exists():
                MagicLinkUnsubscribe.objects.create(email=email)
            MagicLink.objects.filter(email=email, disabled=False).update(disabled=True)
            context["unsubscribed"] = True
        return self.render_to_response(context)


class Logout(RedirectView):
    def get(self, request, *args, **kwargs):
        logout(self.request)

        next_page = get_safe_redirect_url(request, request.GET.get("next", ""))
        if next_page:
            return HttpResponseRedirect(next_page)

        redirect_url = get_url_path(django_settings.LOGOUT_REDIRECT_URL)
        return HttpResponseRedirect(redirect_url)
