from importlib import reload

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.adapter import MagicLinkAdapter, get_adapter
from magiclink.models import MagicLink
from magiclink.signals import spam_detected

User = get_user_model()
calls = []


def allow(request, email, form):
    calls.append(("allow", email))


def reject_bad_domain(request, email, form):
    calls.append(("reject_bad_domain", email))
    if email.endswith("@bad.example"):
        return "Bad domain"
    return None


def never_reached(request, email, form):
    calls.append(("never_reached", email))
    return "Never reached"


@pytest.fixture(autouse=True)
def clear_calls():
    calls.clear()


@pytest.fixture
def use_checks(settings):
    def _use(*names):
        settings.MAGICLINK_SPAM_CHECKS = [f"tests.test_spam_checks.{n}" for n in names]

    return _use


def test_spam_checks_default_empty():
    assert mlsettings.SPAM_CHECKS == []
    assert (
        MagicLinkAdapter().check_request(HttpRequest(), "a@example.com", None) is None
    )


@pytest.mark.parametrize("value", ["tests.check", 1, [1]])
def test_spam_checks_bad_value(settings, value):
    settings.MAGICLINK_SPAM_CHECKS = value
    with pytest.raises(ImproperlyConfigured):
        reload(mlsettings)


def test_checks_get_request_email_and_form(settings, mocker):
    check = mocker.patch("tests.test_spam_checks.allow", return_value=None)
    settings.MAGICLINK_SPAM_CHECKS = ["tests.test_spam_checks.allow"]
    request = HttpRequest()
    form = object()
    assert get_adapter().check_request(request, "a@example.com", form) is None
    check.assert_called_once_with(request, "a@example.com", form)


def test_checks_run_in_order_and_stop_at_first_reason(use_checks):
    use_checks("allow", "reject_bad_domain", "never_reached")
    reason = get_adapter().check_request(HttpRequest(), "a@bad.example", None)
    assert reason == "Bad domain"
    assert [name for name, _ in calls] == ["allow", "reject_bad_domain"]


@pytest.mark.asyncio
async def test_acheck_request_runs_checks(use_checks):
    use_checks("reject_bad_domain")
    reason = await get_adapter().acheck_request(HttpRequest(), "a@bad.example", None)
    assert reason == "Bad domain"


@pytest.mark.django_db
def test_login_rejected_by_check(client, use_checks, mocker):
    handler = mocker.Mock()
    spam_detected.connect(handler, weak=False)
    use_checks("reject_bad_domain")
    user = User.objects.create(username="bad", email="a@bad.example")
    try:
        response = client.post(reverse("magiclink:login"), {"email": user.email})
    finally:
        spam_detected.disconnect(handler)

    assert response.context["login_form"].errors["email"] == ["Bad domain"]
    assert not MagicLink.objects.exists()
    assert mail.outbox == []
    assert handler.call_args.kwargs["reason"] == "Bad domain"


@pytest.mark.django_db
def test_login_rejected_quietly(client, settings, use_checks):
    settings.MAGICLINK_ANTISPAM_QUIET_REJECT = True
    use_checks("reject_bad_domain")
    user = User.objects.create(username="bad", email="a@bad.example")
    response = client.post(reverse("magiclink:login"), {"email": user.email})
    assert response.url == reverse("magiclink:login_sent")
    assert mail.outbox == []


@pytest.mark.django_db
def test_login_allowed_by_checks_sends_email(client, use_checks, user):
    use_checks("allow", "reject_bad_domain")
    response = client.post(reverse("magiclink:login"), {"email": user.email})
    assert response.url == reverse("magiclink:login_sent")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_rejected_by_check_creates_no_user(client, use_checks):
    use_checks("reject_bad_domain")
    data = {"form_name": "SignupFormEmailOnly", "email": "a@bad.example"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.context["SignupFormEmailOnly"].errors["email"] == ["Bad domain"]
    assert not User.objects.filter(email="a@bad.example").exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_signup_allowed_by_check_sends_email(client, use_checks):
    use_checks("reject_bad_domain")
    data = {"form_name": "SignupFormEmailOnly", "email": "good@example.com"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.url == reverse("magiclink:login_sent")
    assert len(mail.outbox) == 1
