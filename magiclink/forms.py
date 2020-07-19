from django import forms
from django.contrib.auth import get_user_model

from . import settings

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'autofocus': 'autofocus', 'placeholder': 'Enter your email'
        })
    )

    def clean_email(self) -> str:
        email = self.cleaned_data['email']

        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        if settings.REQUIRE_SIGNUP:
            users = User.objects.filter(email=email)
            if not users:
                error = 'We could not find a user with that email address'
                raise forms.ValidationError(error)

        return email


class SignupFormEmailOnly(forms.Form):
    form_name = forms.CharField(
        initial='SignupFormEmailOnly', widget=forms.HiddenInput()
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'})
    )

    def clean_email(self) -> str:
        email = self.cleaned_data['email']

        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        users = User.objects.filter(email=email)
        if users:
            raise forms.ValidationError(
                'Email address is already linked to an account'
            )
        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        return email


class SignupForm(SignupFormEmailOnly):
    form_name = forms.CharField(
        initial='SignupForm', widget=forms.HiddenInput()
    )
    name = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Enter your name'})
    )

    field_order = ['form_name', 'name', 'email']


class SignupFormWithUsername(SignupFormEmailOnly):
    form_name = forms.CharField(
        initial='SignupFormWithUsername', widget=forms.HiddenInput()
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Enter your username'})
    )
    field_order = ['form_name', 'username', 'email']

    def clean_username(self) -> str:
        username = self.cleaned_data['username']
        users = User.objects.filter(username=username)
        if users:
            raise forms.ValidationError(
                'username is already linked to an account'
            )
        return username


class SignupFormFull(SignupForm, SignupFormWithUsername):
    form_name = forms.CharField(
        initial='SignupFormFull', widget=forms.HiddenInput()
    )
    field_order = ['form_name', 'username', 'name', 'email']
