import logging

from django.conf import settings as django_settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from . import settings
from .forms import (
    LoginForm,
    SignupForm,
    SignupFormEmailOnly,
    SignupFormFull,
    SignupFormWithUsername,
)
from .helpers import create_magiclink, get_or_create_user
from .models import MagicLink, MagicLinkError
from .utils import get_safe_redirect_url, get_url_path

User = get_user_model()
log = logging.getLogger(__name__)

SIGNUP_FORMS = {
    form.__name__: form
    for form in (
        SignupForm,
        SignupFormEmailOnly,
        SignupFormWithUsername,
        SignupFormFull,
    )
}


@method_decorator(csrf_protect, name="dispatch")
class Login(TemplateView):
    template_name = settings.LOGIN_TEMPLATE_NAME

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["login_form"] = LoginForm()
        context["require_signup"] = settings.REQUIRE_SIGNUP
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        context["require_signup"] = settings.REQUIRE_SIGNUP
        form = LoginForm(request.POST)
        if not form.is_valid():
            context["login_form"] = form
            return self.render_to_response(context)

        email = form.cleaned_data["email"]
        if not settings.REQUIRE_SIGNUP:
            get_or_create_user(email)

        redirect_url = self.login_redirect_url(request.GET.get("next", ""))
        try:
            magiclink = create_magiclink(email, request, redirect_url=redirect_url)
        except MagicLinkError as e:
            form.add_error("email", str(e))
            context["login_form"] = form
            return self.render_to_response(context)

        magiclink.send(request)

        sent_url = get_url_path(settings.LOGIN_SENT_REDIRECT)
        response = HttpResponseRedirect(sent_url)
        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f"magiclink{magiclink.pk}"
            response.set_cookie(cookie_name, magiclink.cookie_value)
            log.info(f"Cookie {cookie_name} set for {email}")
        return response

    def login_redirect_url(self, next_url) -> str:
        return get_safe_redirect_url(self.request, next_url)


class LoginSent(TemplateView):
    template_name = settings.LOGIN_SENT_TEMPLATE_NAME


@method_decorator(never_cache, name="dispatch")
class LoginVerify(TemplateView):
    template_name = settings.LOGIN_FAILED_TEMPLATE_NAME

    def get(self, request, *args, **kwargs):
        token = request.GET.get("token")
        email = request.GET.get("email")
        user = authenticate(request, token=token, email=email)
        if not user:
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

            try:
                magiclink = MagicLink.objects.get(token=token)
            except MagicLink.DoesNotExist:
                error = "A magic link with that token could not be found"
                context["login_error"] = error
                return self.render_to_response(context)

            try:
                magiclink.validate(request, email)
            except MagicLinkError as error:
                context["login_error"] = str(error)

            return self.render_to_response(context)

        login(request, user)
        log.info(f"Login successful for {email}")

        response = self.login_complete_action()
        if settings.REQUIRE_SAME_BROWSER:
            magiclink = MagicLink.objects.get(token=token)
            cookie_name = f"magiclink{magiclink.pk}"
            response.delete_cookie(cookie_name)
        return response

    def login_complete_action(self) -> HttpResponse:
        token = self.request.GET.get("token")
        magiclink = MagicLink.objects.get(token=token)
        return HttpResponseRedirect(magiclink.redirect_url)


@method_decorator(csrf_protect, name="dispatch")
class Signup(TemplateView):
    template_name = settings.SIGNUP_TEMPLATE_NAME

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["SignupForm"] = SignupForm()
        context["SignupFormEmailOnly"] = SignupFormEmailOnly()
        context["SignupFormWithUsername"] = SignupFormWithUsername()
        context["SignupFormFull"] = SignupFormFull()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        form_name = request.POST.get("form_name")
        form_class = SIGNUP_FORMS.get(form_name)
        if form_class is None:
            return HttpResponseRedirect(self.request.path_info)

        form = form_class(request.POST)
        if not form.is_valid():
            context[form_name] = form
            return self.render_to_response(context)

        email = form.cleaned_data["email"]
        full_name = form.cleaned_data.get("name", "")
        try:
            first_name, last_name = full_name.split(" ", 1)
        except ValueError:
            first_name = full_name
            last_name = ""

        get_or_create_user(
            email=email,
            username=form.cleaned_data.get("username", ""),
            first_name=first_name,
            last_name=last_name,
        )
        next_url = get_safe_redirect_url(request, request.GET.get("next", ""))
        if not next_url:
            next_url = get_url_path(settings.SIGNUP_LOGIN_REDIRECT)
        magiclink = create_magiclink(email, request, redirect_url=next_url)
        magiclink.send(request)

        sent_url = get_url_path(settings.LOGIN_SENT_REDIRECT)
        response = HttpResponseRedirect(sent_url)
        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f"magiclink{magiclink.pk}"
            response.set_cookie(cookie_name, magiclink.cookie_value)
            log.info(f"Cookie {cookie_name} set for {email}")
        return response


class Logout(RedirectView):
    def get(self, request, *args, **kwargs):
        logout(self.request)

        next_page = get_safe_redirect_url(request, request.GET.get("next", ""))
        if next_page:
            return HttpResponseRedirect(next_page)

        redirect_url = get_url_path(django_settings.LOGOUT_REDIRECT_URL)
        return HttpResponseRedirect(redirect_url)
