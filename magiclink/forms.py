from time import time

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from . import settings
from .models import MagicLinkUnsubscribe

User = get_user_model()


def sign_load_time(load_time: float) -> str:
    return TimestampSigner(salt="magiclink.antispam").sign(str(load_time))


def validate_empty(value: str) -> None:
    if value:
        raise ValidationError("This field should be empty")


class AntiSpam(forms.Form):
    url = forms.CharField(
        required=False,
        validators=[validate_empty],
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "style": "display: none !important",
            }
        ),
    )
    load_time = forms.CharField(
        label="ALT (antispam field, don't fill out)",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "style": "display: none !important",
            }
        ),
    )

    def clean_load_time(self) -> float:
        signed_load_time: str = self.cleaned_data.get("load_time", "")
        signer = TimestampSigner(salt="magiclink.antispam")
        try:
            load_time = float(
                signer.unsign(signed_load_time, max_age=settings.ANTISPAM_FORM_MAX_AGE)
            )
        except SignatureExpired:
            raise ValidationError("Form has expired, please reload the page") from None
        except BadSignature:
            raise ValidationError("Invalid value") from None

        shown_field_count = 0
        spam_fields = ["load_time", settings.ANTISPAM_HONEYPOT_FIELD]
        for name, field in self.fields.items():
            if field.widget.input_type != "hidden" and name not in spam_fields:
                shown_field_count += 1

        submit_threshold = shown_field_count * settings.ANTISPAM_FIELD_TIME
        if (time() - load_time) < submit_threshold:
            raise ValidationError("Form filled out too fast - bot detected")
        return load_time

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.ANTISPAM_FORMS:
            del self.fields["url"]
            del self.fields["load_time"]
            return

        self.fields["load_time"].initial = sign_load_time(time())
        honeypot_field = settings.ANTISPAM_HONEYPOT_FIELD
        if honeypot_field != "url":
            self.fields = {
                honeypot_field if name == "url" else name: field
                for name, field in self.fields.items()
            }


class LoginForm(AntiSpam):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"autofocus": "autofocus", "placeholder": "Enter your email"}
        )
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"]

        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            if settings.REQUIRE_SIGNUP:
                error = "We could not find a user with that email address"
                raise forms.ValidationError(error) from None
        else:
            is_active = getattr(user, "is_active", True)
            if not settings.IGNORE_IS_ACTIVE_FLAG and not is_active:
                raise forms.ValidationError("This user has been deactivated")

        if not settings.IGNORE_UNSUBSCRIBE_IF_USER:
            try:
                MagicLinkUnsubscribe.objects.get(email=email)
                error = "Email address is on the unsubscribe list"
                raise forms.ValidationError(error)
            except MagicLinkUnsubscribe.DoesNotExist:
                pass

        return email


class SignupFormEmailOnly(AntiSpam):
    form_name = forms.CharField(
        initial="SignupFormEmailOnly", widget=forms.HiddenInput()
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Enter your email"})
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"]

        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        try:
            MagicLinkUnsubscribe.objects.get(email=email)
            error = "Email address is on the unsubscribe list"
            raise forms.ValidationError(error)
        except MagicLinkUnsubscribe.DoesNotExist:
            pass

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return email
        else:
            error = "Email address is already linked to an account"
            is_active = getattr(user, "is_active", True)
            if not settings.IGNORE_IS_ACTIVE_FLAG and not is_active:
                error = "This user has been deactivated"
            raise forms.ValidationError(error)


class SignupForm(SignupFormEmailOnly):
    form_name = forms.CharField(initial="SignupForm", widget=forms.HiddenInput())
    name = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Enter your name"})
    )
    field_order = ["form_name", "name", "email"]


class SignupFormWithUsername(SignupFormEmailOnly):
    form_name = forms.CharField(
        initial="SignupFormWithUsername", widget=forms.HiddenInput()
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Enter your username"})
    )
    field_order = ["form_name", "username", "email"]

    def clean_username(self) -> str:
        username = self.cleaned_data["username"]
        users = User.objects.filter(username=username)
        if users:
            raise forms.ValidationError("username is already linked to an account")
        return username


class SignupFormFull(SignupForm, SignupFormWithUsername):
    form_name = forms.CharField(initial="SignupFormFull", widget=forms.HiddenInput())
    field_order = ["form_name", "username", "name", "email"]
