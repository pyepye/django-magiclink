import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.models import MagicLink
from magiclink.utils import email_domain_allowed

User = get_user_model()
ERROR = "This email address can not be used"


def test_all_domains_allowed_by_default():
    assert email_domain_allowed("a@example.com")


@pytest.mark.parametrize("setting", ["ALLOWED", "BLOCKED"])
@pytest.mark.parametrize("value", ["example.com", 1, [1]])
def test_bad_value(settings, setting, value):
    setattr(settings, f"MAGICLINK_{setting}_EMAIL_DOMAINS", value)
    with pytest.raises(ImproperlyConfigured):
        _ = getattr(mlsettings, f"{setting}_EMAIL_DOMAINS")


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("a@evil.example", False),
        ("a@EVIL.example", False),
        ("a@mail.evil.example", False),
        ("a@deep.mail.evil.example", False),
        ("a@notevil.example", True),
        ("a@evil.example.com", True),
        ("evil.example@good.example", True),
        ('"a@evil.example"@good.example', True),
    ],
)
def test_blocked_domains(settings, email, allowed):
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["evil.example"]
    assert email_domain_allowed(email) is allowed


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("a@corp.example", True),
        ("a@CORP.example", True),
        ("a@uk.corp.example", True),
        ("a@notcorp.example", False),
        ("a@corp.example.evil.com", False),
        ("a@example", False),
    ],
)
def test_allowed_domains(settings, email, allowed):
    settings.MAGICLINK_ALLOWED_EMAIL_DOMAINS = ["corp.example"]
    assert email_domain_allowed(email) is allowed


def test_allowed_subdomain_does_not_allow_its_parent(settings):
    settings.MAGICLINK_ALLOWED_EMAIL_DOMAINS = ["uk.corp.example"]
    assert email_domain_allowed("a@uk.corp.example")
    assert not email_domain_allowed("a@corp.example")


def test_blocked_is_checked_before_allowed(settings):
    settings.MAGICLINK_ALLOWED_EMAIL_DOMAINS = ["corp.example"]
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["temp.corp.example"]
    assert email_domain_allowed("a@corp.example")
    assert not email_domain_allowed("a@temp.corp.example")


def test_setting_values_ignore_case(settings):
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["EVIL.example"]
    assert not email_domain_allowed("a@evil.example")


@pytest.mark.django_db
def test_login_blocked_domain_hides_account_status(client, settings):
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["evil.example"]
    User.objects.create(username="a", email="a@evil.example")
    response = client.post(reverse("magiclink:login"), {"email": "a@evil.example"})
    assert response.context["login_form"].errors["email"] == [ERROR]
    missing = client.post(reverse("magiclink:login"), {"email": "b@evil.example"})
    assert missing.context["login_form"].errors["email"] == [ERROR]
    assert not MagicLink.objects.exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_login_blocked_domain_creates_no_user(client, settings):
    settings.MAGICLINK_REQUIRE_SIGNUP = False
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["evil.example"]
    client.post(reverse("magiclink:login"), {"email": "new@evil.example"})
    assert not User.objects.filter(email="new@evil.example").exists()


@pytest.mark.django_db
def test_login_allowed_domain_sends_email(client, settings):
    settings.MAGICLINK_ALLOWED_EMAIL_DOMAINS = ["corp.example"]
    User.objects.create(username="a", email="a@corp.example")
    url = reverse("magiclink:login")
    assert client.post(url, {"email": "a@corp.example"}).status_code == 302
    assert len(mail.outbox) == 1

    response = client.post(url, {"email": "a@other.example"})
    assert response.context["login_form"].errors["email"] == [ERROR]


@pytest.mark.django_db
def test_signup_blocked_domain(client, settings):
    settings.MAGICLINK_BLOCKED_EMAIL_DOMAINS = ["evil.example"]
    data = {"form_name": "SignupFormEmailOnly", "email": "a@mail.evil.example"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.context["SignupFormEmailOnly"].errors["email"] == [ERROR]
    assert not User.objects.exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_signup_allowed_domain_creates_user(client, settings):
    settings.MAGICLINK_ALLOWED_EMAIL_DOMAINS = ["corp.example"]
    data = {"form_name": "SignupFormEmailOnly", "email": "a@corp.example"}
    assert client.post(reverse("magiclink:signup"), data).status_code == 302
    assert User.objects.filter(email="a@corp.example").exists()
    assert len(mail.outbox) == 1
