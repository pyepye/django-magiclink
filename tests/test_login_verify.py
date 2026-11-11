from urllib.parse import urlencode

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.http.cookie import SimpleCookie
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_login_verify(client, settings, magic_link):
    url = reverse("magiclink:login_verify")
    request = HttpRequest()
    ml = magic_link(request)
    ml.ip_address = "127.0.0.0"  # This is a little hacky
    ml.save()

    params = {"token": ml.token}
    params["email"] = ml.email
    query = urlencode(params)
    url = f"{url}?{query}"

    cookie_name = f"magiclink{ml.pk}"
    client.cookies = SimpleCookie({cookie_name: ml.cookie_value})
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(settings.LOGIN_REDIRECT_URL)
    assert client.cookies[cookie_name].value == ""
    assert client.cookies[cookie_name]["expires"].startswith("Thu, 01 Jan 1970")
    assert client.cookies[cookie_name]["path"] == "/"
    assert response["Referrer-Policy"] == "no-referrer"

    needs_login_url = reverse("needs_login")
    needs_login_response = client.get(needs_login_url)
    assert needs_login_response.status_code == 200


@pytest.mark.django_db
def test_login_verify_with_redirect(client, magic_link):
    url = reverse("magiclink:login_verify")
    request = HttpRequest()
    request.META["SERVER_NAME"] = "127.0.0.1"
    request.META["SERVER_PORT"] = 80
    ml = magic_link(request)
    ml.ip_address = "127.0.0.0"  # This is a little hacky
    redirect_url = reverse("no_login")
    ml.redirect_url = redirect_url
    ml.save()
    url = ml.generate_url(request)

    client.cookies = SimpleCookie({f"magiclink{ml.pk}": ml.cookie_value})
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == redirect_url


@pytest.mark.django_db
def test_login_verify_no_token_404(client, settings):
    settings.MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = ""

    url = reverse("magiclink:login_verify")
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_login_verify_failed(client, settings):
    settings.MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"
    from magiclink import settings as mlsettings

    url = reverse("magiclink:login_verify")
    response = client.get(url)
    assert response.status_code == 200
    context = response.context_data
    assert context["login_error"] == "A magic link with that token could not be found"
    assert context["ONE_TOKEN_PER_USER"] == mlsettings.ONE_TOKEN_PER_USER
    assert context["REQUIRE_SAME_BROWSER"] == mlsettings.REQUIRE_SAME_BROWSER
    assert context["REQUIRE_SAME_IP"] == mlsettings.REQUIRE_SAME_IP
    assert context["ALLOW_SUPERUSER_LOGIN"] == mlsettings.ALLOW_SUPERUSER_LOGIN
    assert context["ALLOW_STAFF_LOGIN"] == mlsettings.ALLOW_STAFF_LOGIN


@pytest.mark.django_db
def test_login_verify_failed_validation(client, settings, magic_link):
    settings.MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"
    from magiclink import settings as mlsettings

    url = reverse("magiclink:login_verify")
    request = HttpRequest()
    ml = magic_link(request)
    params = {"token": ml.token}
    params["email"] = ml.email
    query = urlencode(params)
    url = f"{url}?{query}"

    response = client.get(url)
    assert response.status_code == 200
    context = response.context_data
    assert (
        context["login_error"]
        == "IP address is different from the IP address used to request the magic link"
    )
    assert context["ONE_TOKEN_PER_USER"] == mlsettings.ONE_TOKEN_PER_USER
    assert context["REQUIRE_SAME_BROWSER"] == mlsettings.REQUIRE_SAME_BROWSER
    assert context["REQUIRE_SAME_IP"] == mlsettings.REQUIRE_SAME_IP
    assert context["ALLOW_SUPERUSER_LOGIN"] == mlsettings.ALLOW_SUPERUSER_LOGIN
    assert context["ALLOW_STAFF_LOGIN"] == mlsettings.ALLOW_STAFF_LOGIN


@pytest.mark.django_db
def test_login_verify_failed_redirect(client, settings):
    fail_redirect_url = "/failedredirect"
    settings.MAGICLINK_LOGIN_FAILED_REDIRECT = fail_redirect_url

    url = reverse("magiclink:login_verify")
    response = client.get(url)
    assert response.url == fail_redirect_url


@pytest.mark.django_db
def test_login_verify_custom_verify(client, settings, magic_link):
    settings.MAGICLINK_LOGIN_VERIFY_URL = "custom_login_verify"
    from magiclink import settings

    url = reverse(settings.LOGIN_VERIFY_URL)
    request = HttpRequest()
    request.META["SERVER_NAME"] = "127.0.0.1"
    request.META["SERVER_PORT"] = 80
    ml = magic_link(request)
    ml.ip_address = "127.0.0.0"
    ml.redirect_url = reverse("needs_login")  # Should be ignored
    ml.save()
    url = ml.generate_url(request)

    cookie_name = f"magiclink{ml.pk}"
    client.cookies = SimpleCookie({cookie_name: ml.cookie_value})
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("no_login")
    assert client.cookies[cookie_name].value == ""
    assert client.cookies[cookie_name]["expires"].startswith("Thu, 01 Jan 1970")
    assert client.cookies[cookie_name]["path"] == "/"

    settings.MAGICLINK_LOGIN_VERIFY_URL = "magiclink:login_verify"
    from magiclink import settings


@pytest.mark.django_db
def test_login_verify_failed_no_referrer(client):
    url = reverse("magiclink:login_verify")
    response = client.get(f"{url}?token=fake&email=test@example.com")
    assert response.status_code == 200
    assert response["Referrer-Policy"] == "no-referrer"


@pytest.mark.django_db
def test_login_verify_disabled_link_has_no_other_error(client, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    ml.ip_address = "127.0.0.0"
    ml.disabled = True
    ml.save()
    client.cookies = SimpleCookie({f"magiclink{ml.pk}": ml.cookie_value})

    query = urlencode({"token": ml.token, "email": ml.email})
    response = client.get(f"{reverse('magiclink:login_verify')}?{query}")

    assert response.status_code == 200
    assert response.context["login_error"] == ""
