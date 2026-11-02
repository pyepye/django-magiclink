import logging
from urllib.parse import urlencode

import pytest
from django.http import HttpRequest
from django.urls import reverse

from magiclink.models import MagicLink
from magiclink.utils import clean_ip, get_client_ip, warn_once

PROXY_COUNT = "magiclink.settings.TRUSTED_PROXY_COUNT"
IP_HEADER = "magiclink.settings.TRUSTED_CLIENT_IP_HEADER"


@pytest.fixture(autouse=True)
def reset_warn_once():
    warn_once.cache_clear()


def make_request(**meta):
    request = HttpRequest()
    request.META.update(meta)
    return request


def login(client, user, request_meta, verify_meta):
    client.post(reverse("magiclink:login"), {"email": user.email}, **request_meta)
    magiclink = MagicLink.objects.get(email=user.email)
    query = urlencode({"token": magiclink.token, "email": magiclink.email})
    url = f"{reverse('magiclink:login_verify')}?{query}"
    return magiclink, client.get(url, **verify_meta)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("203.0.113.9", "203.0.113.9"),
        (" 203.0.113.9 ", "203.0.113.9"),
        ("203.0.113.9:5678", "203.0.113.9"),
        ("2001:db8::1", "2001:db8::1"),
        ("2001:DB8::1", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("[2001:db8::1]:5678", "2001:db8::1"),
        ("fe80::1%en0", "fe80::1"),
        ("", None),
        ("not-an-ip", None),
        ("not-an-ip:5678", None),
        ("203.0.113.9:port", None),
        ("203.0.113.999", None),
        ("unix:", None),
    ],
)
def test_clean_ip(value, expected):
    assert clean_ip(value) == expected


def test_get_client_ip_removes_port_from_forwarded_ip(mocker):
    mocker.patch(PROXY_COUNT, 1)
    request = make_request(
        REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8:5678"
    )
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_removes_port_from_trusted_header(mocker):
    mocker.patch(IP_HEADER, "X-Real-IP")
    request = make_request(REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="5.6.7.8:5678")
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_invalid_trusted_header_uses_forwarded_ip(mocker):
    mocker.patch(IP_HEADER, "X-Real-IP")
    mocker.patch(PROXY_COUNT, 1)
    request = make_request(
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_REAL_IP="not-an-ip",
        HTTP_X_FORWARDED_FOR="5.6.7.8",
    )
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_invalid_forwarded_ip_uses_remote_addr(mocker):
    mocker.patch(PROXY_COUNT, 1)
    request = make_request(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="not-an-ip")
    assert get_client_ip(request) == "10.0.0.1"


@pytest.mark.parametrize("meta", [{}, {"REMOTE_ADDR": ""}, {"REMOTE_ADDR": "unix:"}])
def test_get_client_ip_warns_if_no_ip(caplog, meta):
    caplog.set_level(logging.WARNING, logger="magiclink")
    assert get_client_ip(make_request(**meta)) is None
    assert "MAGICLINK_TRUSTED_PROXY_COUNT" in caplog.text
    assert "MAGICLINK_TRUSTED_CLIENT_IP_HEADER" in caplog.text


def test_get_client_ip_does_not_warn_if_ip_found(caplog):
    caplog.set_level(logging.WARNING, logger="magiclink")
    assert get_client_ip(make_request(REMOTE_ADDR="10.0.0.1")) == "10.0.0.1"
    assert not caplog.text


def test_get_client_ip_warns_once_if_forwarded_ip_is_ignored(caplog):
    caplog.set_level(logging.WARNING, logger="magiclink")
    request = make_request(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4")
    assert get_client_ip(request) == "10.0.0.1"
    assert get_client_ip(request) == "10.0.0.1"
    assert caplog.text.count("X-Forwarded-For is ignored") == 1


@pytest.mark.parametrize(
    ("setting", "value"), [(PROXY_COUNT, 1), (IP_HEADER, "X-Real-IP")]
)
def test_get_client_ip_does_not_warn_if_a_proxy_is_set(mocker, caplog, setting, value):
    mocker.patch(setting, value)
    caplog.set_level(logging.WARNING, logger="magiclink")
    get_client_ip(make_request(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4"))
    assert not caplog.text


@pytest.mark.django_db
def test_login_with_no_ip_address(client, user):
    no_ip = {"REMOTE_ADDR": ""}
    magiclink, response = login(client, user, no_ip, no_ip)
    assert magiclink.ip_address is None
    assert response.status_code == 302


@pytest.mark.django_db
def test_login_fails_if_ip_address_appears(client, user):
    _, response = login(client, user, {"REMOTE_ADDR": ""}, {"REMOTE_ADDR": "10.0.0.1"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_fails_if_ip_address_disappears(client, user):
    _, response = login(client, user, {"REMOTE_ADDR": "10.0.0.1"}, {"REMOTE_ADDR": ""})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_when_proxy_changes_the_port(mocker, client, user):
    mocker.patch(PROXY_COUNT, 1)
    magiclink, response = login(
        client,
        user,
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9:5678"},
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9:6000"},
    )
    assert magiclink.ip_address == "203.0.113.0"
    assert response.status_code == 302


@pytest.mark.django_db
def test_port_is_not_stored_if_ip_not_anonymised(mocker, client, user):
    mocker.patch(PROXY_COUNT, 1)
    mocker.patch("magiclink.settings.ANONYMIZE_IP", False)
    magiclink, response = login(
        client,
        user,
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9:5678"},
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9:6000"},
    )
    assert magiclink.ip_address == "203.0.113.9"
    assert response.status_code == 302


@pytest.mark.django_db
def test_login_fails_if_proxy_sends_a_different_ip(mocker, client, user):
    mocker.patch(PROXY_COUNT, 1)
    _, response = login(
        client,
        user,
        {"HTTP_X_FORWARDED_FOR": "203.0.113.9:5678"},
        {"HTTP_X_FORWARDED_FOR": "198.51.100.9:5678"},
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_invalid_forwarded_ip_uses_remote_addr_for_the_link(mocker, client, user):
    mocker.patch(PROXY_COUNT, 1)
    meta = {"REMOTE_ADDR": "10.0.0.1", "HTTP_X_FORWARDED_FOR": "not-an-ip"}
    magiclink, response = login(client, user, meta, meta)
    assert magiclink.ip_address == "10.0.0.0"
    assert response.status_code == 302
