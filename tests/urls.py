from django import forms
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, HttpResponseRedirect
from django.urls import include, path, reverse

from magiclink.forms import LoginForm, SignupForm
from magiclink.views import Login, LoginVerify, Signup


@login_required
def needs_login(request):
    return HttpResponse()


def no_login(request):
    return HttpResponse()


class ViewAttributeLoginForm(LoginForm):
    code = forms.CharField()


class ViewAttributeSignupForm(SignupForm):
    code = forms.CharField()


class CustomLoginVerify(LoginVerify):
    def login_complete_action(self) -> HttpResponse:
        url = reverse("no_login")
        return HttpResponseRedirect(url)


urlpatterns = [
    path("no-login/", no_login, name="no_login"),
    path("needs-login/", needs_login, name="needs_login"),
    path(
        "custom-login-verify/", CustomLoginVerify.as_view(), name="custom_login_verify"
    ),
    path(
        "form-class-login/",
        Login.as_view(form_class=ViewAttributeLoginForm),
        name="form_class_login",
    ),
    path(
        "form-class-signup/",
        Signup.as_view(form_class=ViewAttributeSignupForm),
        name="form_class_signup",
    ),
    path("auth/", include("magiclink.urls", namespace="magiclink")),
]
