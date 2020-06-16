import logging

from django.conf import settings as django_settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from . import settings
from .forms import (
    LoginForm, SignupForm, SignupFormEmailOnly, SignupFormFull,
    SignupFormWithUsername
)
from .helpers import create_magiclink, get_or_create_user
from .models import MagicLink

User = get_user_model()
log = logging.getLogger(__name__)


class Login(TemplateView):
    template_name = 'login.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['login_form'] = LoginForm(request.POST)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        form = LoginForm(request.POST)
        if not form.is_valid():
            context['login_form'] = form
            return self.render_to_response(context)

        email = form.cleaned_data['email']
        if not settings.REQUIRE_SIGNUP:
            get_or_create_user(email)

        next_url = request.GET.get('next', '')

        magic_link = create_magiclink(email, request, redirect_url=next_url)
        magic_link.send(request)

        sent_url = reverse('magiclink:login_sent')
        if settings.LOGIN_SENT_REDIRECT:
            sent_url = settings.LOGIN_SENT_REDIRECT
        return HttpResponseRedirect(sent_url)


class LoginSent(TemplateView):
    template_name = 'login_sent.html'


class LoginVerify(RedirectView):

    def get(self, request, *args, **kwargs):
        token = request.GET.get('token')
        if not token:
            raise Http404()

        email = request.GET.get('email')
        user = authenticate(request, token=token, email=email)
        if not user:
            raise Http404()

        login(request, user)

        magic_link = MagicLink.objects.get(token=token)

        return HttpResponseRedirect(magic_link.redirect_url)


class Signup(TemplateView):
    template_name = 'signup.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['SignupForm'] = SignupForm()
        context['SignupFormEmailOnly'] = SignupFormEmailOnly()
        context['SignupFormWithUsername'] = SignupFormWithUsername()
        context['SignupFormFull'] = SignupFormFull()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        logout(request)
        context = self.get_context_data(**kwargs)
        form_name = request.POST.get('form_name')
        from_list = [
            'SignupForm, SignupFormEmailOnly', 'SignupFormWithUsername',
            'SignupFormFull',
        ]
        forms = __import__('magiclink.forms', fromlist=from_list)
        Form = getattr(forms, form_name)

        form = Form(request.POST)
        if not form.is_valid():
            context[form_name] = form
            return self.render_to_response(context)

        email = form.cleaned_data['email']
        full_name = form.cleaned_data.get('name', '')
        try:
            first_name, last_name = full_name.split(' ', 1)
        except ValueError:
            first_name = full_name
            last_name = ''

        get_or_create_user(
            email=email,
            username=form.cleaned_data.get('username', ''),
            first_name=first_name,
            last_name=last_name
        )
        next_url = request.GET.get('next', settings.SIGNUP_REDIRECT)
        magic_link = create_magiclink(email, request, redirect_url=next_url)
        magic_link.send(request)

        sent_url = reverse('magiclink:login_sent')
        if settings.LOGIN_SENT_REDIRECT:
            sent_url = settings.LOGIN_SENT_REDIRECT
        return HttpResponseRedirect(sent_url)


class Logout(RedirectView):

    def get(self, request, *args, **kwargs):
        logout(self.request)
        return HttpResponseRedirect(django_settings.LOGOUT_REDIRECT_URL)
