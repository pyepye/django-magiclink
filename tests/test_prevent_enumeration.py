import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.models import MagicLink, MagicLinkUnsubscribe

User = get_user_model()


@pytest.fixture
def prevent(settings):
    settings.MAGICLINK_PREVENT_ENUMERATION = True


def visible(response):
    cookies = {
        re.sub(r"\d+", "N", name): {
            key: morsel[key] for key in ("httponly", "secure", "samesite", "path")
        }
        for name, morsel in response.cookies.items()
    }
    return response.status_code, response.get("Location"), response.content, cookies


def active(email="active@example.com"):
    return User.objects.create(username=email, email=email)


def inactive(email="inactive@example.com"):
    return User.objects.create(username=email, email=email, is_active=False)


def unsubscribed(email="unsubscribed@example.com"):
    MagicLinkUnsubscribe.objects.create(email=email)
    return User.objects.create(username=email, email=email)


def test_prevent_enumeration_off_by_default():
    assert mlsettings.PREVENT_ENUMERATION is False


@pytest.mark.django_db
def test_login_errors_are_shown_when_off(client):
    response = client.post(reverse("magiclink:login"), {"email": "no@example.com"})
    assert response.status_code == 200
    assert not MagicLink.objects.exists()


@pytest.mark.django_db
def test_login_responses_are_the_same_for_all_accounts(prevent):
    url = reverse("magiclink:login")
    expected = visible(Client().post(url, {"email": active().email}))
    assert expected[0] == 302
    assert expected[3]
    assert len(mail.outbox) == 1

    for email in (
        "unknown@example.com",
        inactive().email,
        unsubscribed().email,
    ):
        assert visible(Client().post(url, {"email": email})) == expected
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_login_cookie_number_goes_up_by_one_for_all_accounts(prevent):
    url = reverse("magiclink:login")
    emails = [active().email, "unknown@example.com", inactive().email]
    numbers = []
    for email in emails:
        response = Client().post(url, {"email": email})
        numbers.append(int(re.search(r"\d+", next(iter(response.cookies))).group()))
    assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2]


@pytest.mark.django_db
def test_login_repeat_request_is_the_same_for_all_accounts(prevent):
    url = reverse("magiclink:login")
    known = Client()
    known.post(url, {"email": active().email})
    unknown = Client()
    unknown.post(url, {"email": "unknown@example.com"})

    first = visible(known.post(url, {"email": "active@example.com"}))
    second = visible(unknown.post(url, {"email": "unknown@example.com"}))
    assert first == second
    assert first[3] == {}


@pytest.mark.django_db
def test_login_repeat_after_used_link_redirects(prevent, client):
    url = reverse("magiclink:login")
    client.post(url, {"email": active().email})
    MagicLink.objects.update(disabled=True)
    response = client.post(url, {"email": "active@example.com"})
    assert response.status_code == 302
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_login_without_signup_does_not_create_unsubscribed_user(prevent, settings):
    settings.MAGICLINK_REQUIRE_SIGNUP = False
    MagicLinkUnsubscribe.objects.create(email="new@example.com")
    Client().post(reverse("magiclink:login"), {"email": "new@example.com"})
    assert not User.objects.filter(email="new@example.com").exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_login_without_signup_still_creates_new_user(prevent, settings):
    settings.MAGICLINK_REQUIRE_SIGNUP = False
    Client().post(reverse("magiclink:login"), {"email": "new@example.com"})
    assert User.objects.filter(email="new@example.com").exists()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_other_login_errors_are_still_shown(prevent, client):
    response = client.post(reverse("magiclink:login"), {"email": "not-an-email"})
    assert response.status_code == 200
    assert "email" in response.context["login_form"].errors


def signup_data(email):
    return {"form_name": "SignupForm", "name": "New Name", "email": email}


@pytest.mark.django_db
def test_signup_responses_are_the_same_for_all_accounts(prevent):
    url = reverse("magiclink:signup")
    expected = visible(Client().post(url, signup_data("new@example.com")))
    assert expected[0] == 302
    assert User.objects.filter(email="new@example.com").exists()
    assert len(mail.outbox) == 1

    for email in (active().email, inactive().email, unsubscribed().email):
        assert visible(Client().post(url, signup_data(email))) == expected


@pytest.mark.django_db
def test_signup_with_existing_email_sends_a_working_login_link(prevent, client):
    user = active()
    client.post(reverse("magiclink:signup"), signup_data(user.email))

    user.refresh_from_db()
    assert user.first_name == ""
    assert User.objects.filter(email=user.email).count() == 1
    assert mail.outbox[0].to == [user.email]

    link = re.search(r"http://\S+", mail.outbox[0].body).group()
    assert client.get(link).status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.parametrize("make_user", [inactive, unsubscribed])
@pytest.mark.django_db
def test_signup_sends_nothing_to_blocked_accounts(prevent, client, make_user):
    user = make_user()
    client.post(reverse("magiclink:signup"), signup_data(user.email))
    assert mail.outbox == []
    assert User.objects.filter(email=user.email).count() == 1


@pytest.mark.django_db
def test_signup_unsubscribed_new_email_creates_no_user(prevent, client):
    MagicLinkUnsubscribe.objects.create(email="new@example.com")
    client.post(reverse("magiclink:signup"), signup_data("new@example.com"))
    assert not User.objects.filter(email="new@example.com").exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_signup_repeat_request_redirects(prevent, client):
    url = reverse("magiclink:signup")
    data = signup_data(active().email)
    client.post(url, data)
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse("magiclink:login_sent")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_too_many_requests_raises_when_off(client, mocker):
    from magiclink.models import MagicLinkError

    mocker.patch("magiclink.views.create_magiclink", side_effect=MagicLinkError)
    with pytest.raises(MagicLinkError):
        client.post(reverse("magiclink:signup"), signup_data("new@example.com"))


@pytest.mark.django_db
def test_login_sent_page_text(client, settings):
    url = reverse("magiclink:login_sent")
    assert b"We have sent you" in client.get(url).content
    settings.MAGICLINK_PREVENT_ENUMERATION = True
    assert b"If there is an account" in client.get(url).content
