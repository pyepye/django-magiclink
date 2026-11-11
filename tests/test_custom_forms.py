import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.forms import LoginForm, SignupForm, SignupFormEmailOnly
from magiclink.models import MagicLink
from tests.urls import ViewAttributeLoginForm, ViewAttributeSignupForm

User = get_user_model()


class CaptchaLoginForm(LoginForm):
    captcha = forms.CharField()


class CaptchaSignupForm(SignupForm):
    captcha = forms.CharField()


class CaptchaEmailOnlyForm(SignupFormEmailOnly):
    captcha = forms.CharField()


@pytest.fixture
def custom_forms(settings):
    settings.MAGICLINK_FORMS = {
        "login": "tests.test_custom_forms.CaptchaLoginForm",
        "signup": "tests.test_custom_forms.CaptchaSignupForm",
    }


def test_default_forms_setting():
    assert mlsettings.FORMS == {}


@pytest.mark.parametrize("value", ["x", {"other": "x"}, {"login": 1}])
def test_forms_bad_value(settings, value):
    settings.MAGICLINK_FORMS = value
    with pytest.raises(ImproperlyConfigured):
        _ = mlsettings.FORMS


@pytest.mark.django_db
def test_login_page_shows_custom_form(client, custom_forms):
    response = client.get(reverse("magiclink:login"))
    assert type(response.context["login_form"]) is CaptchaLoginForm
    assert b'name="captcha"' in response.content


@pytest.mark.django_db
def test_login_custom_form_is_validated(client, custom_forms, user):
    response = client.post(reverse("magiclink:login"), {"email": user.email})
    assert response.status_code == 200
    assert "captcha" in response.context["login_form"].errors
    assert not MagicLink.objects.exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_login_custom_form_sends_email(client, custom_forms, user):
    data = {"email": user.email, "captcha": "ok"}
    response = client.post(reverse("magiclink:login"), data)
    assert response.url == reverse("magiclink:login_sent")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_page_shows_custom_form_for_every_name(client, custom_forms):
    response = client.get(reverse("magiclink:signup"))
    for name in (
        "SignupForm",
        "SignupFormEmailOnly",
        "SignupFormWithUsername",
        "SignupFormFull",
    ):
        assert type(response.context[name]) is CaptchaSignupForm
    assert b'name="captcha"' in response.content


@pytest.mark.django_db
def test_signup_custom_form_is_validated(client, custom_forms):
    data = {"form_name": "SignupForm", "name": "A", "email": "new@example.com"}
    response = client.post(reverse("magiclink:signup"), data)
    assert "captcha" in response.context["SignupForm"].errors
    assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.parametrize(
    "form_name", ["SignupFormEmailOnly", "SignupFormFull", "made-up", ""]
)
@pytest.mark.django_db
def test_signup_can_not_avoid_custom_form_with_another_form_name(
    client, custom_forms, form_name
):
    data = {"form_name": form_name, "name": "A", "email": "new@example.com"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.status_code == 200
    assert "captcha" in response.context["SignupForm"].errors
    assert "captcha" in response.context["SignupFormEmailOnly"].errors
    assert not User.objects.filter(email="new@example.com").exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_signup_custom_form_creates_user_and_sends_email(client, custom_forms):
    data = {
        "form_name": "SignupForm",
        "name": "A B",
        "email": "new@example.com",
        "captcha": "ok",
    }
    response = client.post(reverse("magiclink:signup"), data)
    assert response.url == reverse("magiclink:login_sent")
    assert User.objects.get(email="new@example.com").last_name == "B"
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_custom_form_without_signup_form_name(client, settings):
    settings.MAGICLINK_FORMS = {
        "signup": "tests.test_custom_forms.CaptchaEmailOnlyForm"
    }
    data = {
        "form_name": "SignupFormEmailOnly",
        "email": "new@example.com",
    }
    response = client.post(reverse("magiclink:signup"), data)
    assert "captcha" in response.context["SignupForm"].errors


@pytest.mark.django_db
def test_login_custom_only_keeps_default_signup(client, settings):
    settings.MAGICLINK_FORMS = {"login": "tests.test_custom_forms.CaptchaLoginForm"}
    data = {"form_name": "SignupFormEmailOnly", "email": "new@example.com"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.url == reverse("magiclink:login_sent")


@pytest.mark.django_db
def test_form_class_on_login_view(client, user):
    url = reverse("form_class_login")
    assert type(client.get(url).context["login_form"]) is ViewAttributeLoginForm
    response = client.post(url, {"email": user.email})
    assert "code" in response.context["login_form"].errors


@pytest.mark.django_db
def test_form_class_on_view_is_used_before_setting(client, custom_forms):
    response = client.get(reverse("form_class_signup"))
    assert type(response.context["SignupForm"]) is ViewAttributeSignupForm
