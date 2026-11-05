import re
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.signing import TimestampSigner
from django.http import HttpRequest
from django.test import Client
from django.urls import reverse

from magiclink.helpers import acreate_magiclink, create_magiclink
from magiclink.models import (
    MagicLink,
    MagicLinkUnsubscribe,
    sign_unsubscribe_email,
    unsign_unsubscribe_email,
)

User = get_user_model()
TEXT = "Stop these emails"


@pytest.fixture
def link_on(settings):
    settings.MAGICLINK_UNSUBSCRIBE_LINK = True


def unsubscribe_url(email):
    query = urlencode({"email": sign_unsubscribe_email(email)})
    return f"{reverse('magiclink:unsubscribe')}?{query}"


def email_urls(message):
    return re.findall(r"http://\S+", message.body)


def test_signed_email_round_trip():
    assert unsign_unsubscribe_email(sign_unsubscribe_email("a@b.com")) == "a@b.com"


def test_signed_email_tampered():
    with pytest.raises(signing.BadSignature):
        unsign_unsubscribe_email(sign_unsubscribe_email("a@b.com") + "x")


def test_signature_for_other_purposes_is_rejected():
    with pytest.raises(signing.BadSignature):
        unsign_unsubscribe_email(signing.dumps("a@b.com"))
    with pytest.raises(signing.BadSignature):
        unsign_unsubscribe_email(TimestampSigner(salt="magiclink.antispam").sign("1"))


@pytest.mark.django_db
def test_no_link_in_email_by_default(client, user):
    client.post(reverse("magiclink:login"), {"email": user.email})
    message = mail.outbox[0]
    assert TEXT not in message.body
    assert TEXT not in message.alternatives[0][0]


@pytest.mark.django_db
def test_link_in_text_and_html_email(client, link_on, user):
    client.post(reverse("magiclink:login"), {"email": user.email})
    message = mail.outbox[0]
    assert TEXT in message.body
    assert TEXT in message.alternatives[0][0]
    assert "/auth/unsubscribe/?email=" in message.alternatives[0][0]
    assert len(email_urls(message)) == 2


@pytest.mark.django_db
def test_no_link_when_unsubscribe_is_ignored_for_users(client, settings, link_on, user):
    settings.MAGICLINK_IGNORE_UNSUBSCRIBE_IF_USER = True
    client.post(reverse("magiclink:login"), {"email": user.email})
    assert TEXT not in mail.outbox[0].body


@pytest.mark.django_db
def test_url_uses_site_url_not_the_host_header(settings, link_on, user):
    settings.MAGICLINK_SITE_URL = "https://example.com"
    request = HttpRequest()
    request.META["HTTP_HOST"] = "evil.example"
    url = create_magiclink(user.email, request).generate_unsubscribe_url(request)
    assert url.startswith("https://example.com/auth/unsubscribe/?email=")


@pytest.mark.django_db
def test_url_holds_the_signed_email(rf, link_on, user):
    request = rf.get("/")
    url = create_magiclink(user.email, request).generate_unsubscribe_url(request)
    value = parse_qs(urlparse(url).query)["email"][0]
    assert unsign_unsubscribe_email(value) == user.email


@pytest.mark.django_db
def test_get_shows_page_and_changes_nothing(client, user, rf):
    link = create_magiclink(user.email, rf.get("/"))
    response = client.get(unsubscribe_url(user.email))
    assert response.status_code == 200
    assert response.template_name == ["magiclink/unsubscribe.html"]
    assert response.context["email"] == user.email
    assert b'<form method="post">' in response.content
    assert not MagicLinkUnsubscribe.objects.exists()
    link.refresh_from_db()
    assert not link.disabled


@pytest.mark.django_db
def test_post_unsubscribes_and_disables_links(client, user, rf):
    link = create_magiclink(user.email, rf.get("/"))
    response = client.post(unsubscribe_url(user.email))
    assert response.status_code == 200
    assert response.context["unsubscribed"] is True
    assert MagicLinkUnsubscribe.objects.filter(email=user.email).count() == 1
    link.refresh_from_db()
    assert link.disabled


@pytest.mark.django_db
def test_post_twice_adds_one_row(client, user):
    url = unsubscribe_url(user.email)
    client.post(url)
    assert client.post(url).status_code == 200
    assert MagicLinkUnsubscribe.objects.filter(email=user.email).count() == 1


@pytest.mark.parametrize("value", ["", "?email=bad", "?email=a@example.com"])
@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.django_db
def test_invalid_link(client, method, value):
    url = reverse("magiclink:unsubscribe") + value
    response = getattr(client, method)(url)
    assert response.status_code == 400
    assert response.context["invalid_link"] is True
    assert not MagicLinkUnsubscribe.objects.exists()


@pytest.mark.django_db
def test_post_needs_csrf_token(user):
    url = unsubscribe_url(user.email)
    assert Client(enforce_csrf_checks=True).post(url).status_code == 403
    assert not MagicLinkUnsubscribe.objects.exists()


@pytest.mark.django_db
def test_template_setting(client, settings, user):
    settings.MAGICLINK_UNSUBSCRIBE_TEMPLATE_NAME = "magiclink/login_sent.html"
    response = client.get(unsubscribe_url(user.email))
    assert response.template_name == ["magiclink/login_sent.html"]


@pytest.mark.django_db
def test_full_flow_with_scanner(link_on, user):
    browser = Client(enforce_csrf_checks=True)
    page = browser.get(reverse("magiclink:login"))
    browser.post(
        reverse("magiclink:login"),
        {"email": user.email, "csrfmiddlewaretoken": str(page.context["csrf_token"])},
    )
    login_url, stop_url = email_urls(mail.outbox[0])

    scanner = Client(REMOTE_ADDR="198.51.100.9")
    assert scanner.get(stop_url).status_code == 200
    assert not MagicLinkUnsubscribe.objects.exists()

    page = browser.get(stop_url)
    assert b"Stop these emails" in page.content
    response = browser.post(
        stop_url, {"csrfmiddlewaretoken": str(page.context["csrf_token"])}
    )
    assert b"You have been unsubscribed" in response.content
    assert MagicLinkUnsubscribe.objects.filter(email=user.email).exists()

    assert browser.get(login_url).status_code == 200
    assert "_auth_user_id" not in browser.session

    page = browser.get(reverse("magiclink:login"))
    response = browser.post(
        reverse("magiclink:login"),
        {"email": user.email, "csrfmiddlewaretoken": str(page.context["csrf_token"])},
    )
    assert "unsubscribe" in str(response.context["login_form"].errors)
    assert len(mail.outbox) == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_asend_includes_the_link(rf, link_on, user):
    request = rf.get("/")
    ml = await acreate_magiclink(user.email, request)
    await ml.asend(request)
    assert TEXT in mail.outbox[0].body
    assert await MagicLink.objects.acount() == 1
