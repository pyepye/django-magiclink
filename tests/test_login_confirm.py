import re
from importlib import reload

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.models import MagicLink
from magiclink.signals import login_failed

User = get_user_model()


@pytest.fixture
def confirm_on(settings):
    settings.MAGICLINK_LOGIN_CONFIRM = True


def request_link(client, user):
    client.post(reverse("magiclink:login"), {"email": user.email})
    return re.search(r"http://\S+", mail.outbox[-1].body).group()


def test_login_confirm_bad_value(settings):
    settings.MAGICLINK_LOGIN_CONFIRM = "Test"
    with pytest.raises(ImproperlyConfigured):
        reload(mlsettings)


@pytest.mark.django_db
def test_confirm_off_get_logs_in_and_post_is_not_allowed(client, user):
    link = request_link(client, user)
    assert client.post(link).status_code == 405
    assert "_auth_user_id" not in client.session

    response = client.get(link)
    assert response.status_code == 302
    assert response["Referrer-Policy"] == "no-referrer"
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_get_shows_confirm_page_and_does_not_use_the_link(client, confirm_on, user):
    link = request_link(client, user)
    response = client.get(link)

    assert response.status_code == 200
    assert response.template_name == ["magiclink/login_confirm.html"]
    assert b'<form method="post">' in response.content
    assert "_auth_user_id" not in client.session

    ml = MagicLink.objects.get(email=user.email)
    assert not ml.disabled
    assert ml.times_used == 0


@pytest.mark.django_db
def test_confirm_template_setting(client, settings, confirm_on, user):
    settings.MAGICLINK_LOGIN_CONFIRM_TEMPLATE_NAME = "magiclink/login_sent.html"
    response = client.get(request_link(client, user))
    assert response.template_name == ["magiclink/login_sent.html"]


@pytest.mark.django_db
def test_confirm_page_keeps_the_token_out_of_the_referer(client, confirm_on, user):
    response = client.get(request_link(client, user))
    assert response["Referrer-Policy"] == "strict-origin"
    assert response["Cache-Control"].startswith("max-age=0")


@pytest.mark.django_db
def test_scanner_does_not_use_up_the_link(client, confirm_on, user, mocker):
    handler = mocker.Mock()
    login_failed.connect(handler, weak=False)
    link = request_link(client, user)

    scanner = Client(REMOTE_ADDR="198.51.100.9")
    try:
        assert scanner.get(link).status_code == 200
        assert scanner.head(link).status_code == 200
    finally:
        login_failed.disconnect(handler)
    handler.assert_not_called()

    assert client.get(link).status_code == 200
    response = client.post(link)
    assert response.status_code == 302
    assert response.url == reverse("needs_login")
    assert response["Referrer-Policy"] == "no-referrer"
    assert client.session["_auth_user_id"] == str(user.pk)
    assert client.get(reverse("needs_login")).status_code == 200


@pytest.mark.django_db
def test_post_can_not_use_the_link_twice(client, confirm_on, user):
    link = request_link(client, user)
    assert client.post(link).status_code == 302

    client.logout()
    response = client.post(link)
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert response.template_name == ["magiclink/login_failed.html"]


@pytest.mark.django_db
def test_post_from_another_browser_fails(client, confirm_on, user):
    link = request_link(client, user)
    other = Client()
    response = other.post(link)
    assert response.status_code == 200
    assert "_auth_user_id" not in other.session
    assert "Browser is different" in response.context["login_error"]


@pytest.mark.django_db
def test_custom_verify_view_with_confirm(client, settings, confirm_on, user):
    settings.MAGICLINK_LOGIN_VERIFY_URL = "custom_login_verify"
    link = request_link(client, user)
    assert client.get(link).status_code == 200
    response = client.post(link)
    assert response.url == reverse("no_login")


@pytest.fixture
def csrf_client():
    return Client(enforce_csrf_checks=True)


def csrf_flow(csrf_client, user, **post_kwargs):
    login_url = reverse("magiclink:login")
    page = csrf_client.get(login_url)
    csrf_client.post(
        login_url,
        {"email": user.email, "csrfmiddlewaretoken": str(page.context["csrf_token"])},
    )
    link = re.search(r"http://\S+", mail.outbox[-1].body).group()
    page = csrf_client.get(link, secure=True)
    token = str(page.context["csrf_token"])
    return csrf_client.post(
        link, {"csrfmiddlewaretoken": token}, secure=True, **post_kwargs
    )


@pytest.mark.django_db
def test_post_needs_csrf_token(csrf_client, confirm_on, user):
    link = request_link(Client(), user)
    assert csrf_client.post(link).status_code == 403


@pytest.mark.django_db
def test_browser_post_passes_csrf_check_on_https(csrf_client, confirm_on, user):
    response = csrf_flow(csrf_client, user, headers={"origin": "https://testserver"})
    assert response.status_code == 302
    assert csrf_client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_null_origin_from_no_referrer_page_fails_csrf_check(
    csrf_client, confirm_on, user
):
    response = csrf_flow(csrf_client, user, headers={"origin": "null"})
    assert response.status_code == 403
