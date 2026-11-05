from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from magiclink.admin import MagicLinkAdmin
from magiclink.models import MagicLink, MagicLinkUnsubscribe

User = get_user_model()
CHANGELIST = "admin:magiclink_magiclink_changelist"


def make_link(email="a@example.com", ip="10.0.0.0", disabled=False, minutes=5):
    return MagicLink.objects.create(
        email=email,
        token=f"secret-token-{email}-{minutes}-{disabled}",
        cookie_value=f"secret-cookie-{email}-{minutes}-{disabled}",
        expiry=timezone.now() + timedelta(minutes=minutes),
        redirect_url="/",
        ip_address=ip,
        disabled=disabled,
    )


def listed(response):
    return {link.pk for link in response.context["cl"].result_list}


def test_models_are_registered():
    assert admin.site.is_registered(MagicLink)
    assert admin.site.is_registered(MagicLinkUnsubscribe)


@pytest.mark.django_db
def test_changelist_hides_secrets(admin_client):
    ml = make_link()
    response = admin_client.get(reverse(CHANGELIST))
    assert response.status_code == 200
    assert ml.email.encode() in response.content
    assert ml.token.encode() not in response.content
    assert ml.cookie_value.encode() not in response.content


@pytest.mark.django_db
def test_detail_page_hides_secrets_and_can_not_be_changed(admin_client):
    ml = make_link()
    url = reverse("admin:magiclink_magiclink_change", args=[ml.pk])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert ml.email.encode() in response.content
    assert ml.token.encode() not in response.content
    assert ml.cookie_value.encode() not in response.content

    assert admin_client.post(url, {"email": "new@example.com"}).status_code == 403
    ml.refresh_from_db()
    assert ml.email == "a@example.com"


@pytest.mark.django_db
def test_magic_links_can_not_be_added(admin_client):
    url = reverse("admin:magiclink_magiclink_add")
    assert admin_client.get(url).status_code == 403


@pytest.mark.django_db
def test_search_by_email_and_ip(admin_client):
    first = make_link("a@example.com", "10.0.0.0")
    second = make_link("b@example.com", "192.0.2.0")
    url = reverse(CHANGELIST)
    assert listed(admin_client.get(url, {"q": "a@example"})) == {first.pk}
    assert listed(admin_client.get(url, {"q": "192.0.2"})) == {second.pk}


@pytest.mark.django_db
def test_search_does_not_find_tokens(admin_client):
    make_link()
    response = admin_client.get(reverse(CHANGELIST), {"q": "secret-token"})
    assert listed(response) == set()


@pytest.mark.django_db
def test_status_filter(admin_client):
    live = make_link("live@example.com")
    expired = make_link("expired@example.com", minutes=-5)
    disabled = make_link("disabled@example.com", disabled=True)
    url = reverse(CHANGELIST)
    assert listed(admin_client.get(url, {"status": "live"})) == {live.pk}
    assert listed(admin_client.get(url, {"status": "expired"})) == {expired.pk}
    assert listed(admin_client.get(url, {"status": "disabled"})) == {disabled.pk}
    assert len(listed(admin_client.get(url))) == 3


@pytest.mark.django_db
def test_status_column():
    model_admin = MagicLinkAdmin(MagicLink, admin.site)
    assert model_admin.status(make_link("l@example.com")) == "Live"
    assert model_admin.status(make_link("e@example.com", minutes=-5)) == "Expired"
    assert model_admin.status(make_link("d@example.com", disabled=True)) == "Disabled"


def run_action(client, *links):
    return client.post(
        reverse(CHANGELIST),
        {
            "action": "unsubscribe",
            "_selected_action": [link.pk for link in links],
        },
        follow=True,
    )


@pytest.mark.django_db
def test_unsubscribe_action(admin_client):
    first = make_link("a@example.com")
    repeat = make_link("a@example.com", minutes=6)
    second = make_link("b@example.com")
    make_link("not-selected@example.com")
    MagicLinkUnsubscribe.objects.create(email="b@example.com")

    response = run_action(admin_client, first, repeat, second)

    emails = list(MagicLinkUnsubscribe.objects.values_list("email", flat=True))
    assert sorted(emails) == ["a@example.com", "b@example.com"]
    assert b"1 email addresses unsubscribed" in response.content


@pytest.mark.django_db
def test_unsubscribe_action_stops_login_emails(admin_client, client, user):
    ml = make_link(user.email)
    run_action(admin_client, ml)
    response = client.post(reverse("magiclink:login"), {"email": user.email})
    assert "unsubscribe" in str(response.context["login_form"].errors)


@pytest.mark.django_db
def test_unsubscribe_action_needs_add_permission(client, mocker):
    # The custom user models in tests/models.py take over the reverse accessors
    # of auth.User.user_permissions, so real permissions can not be stored here
    mocker.patch.object(
        User, "has_perm", lambda self, perm, obj=None: perm.endswith("view_magiclink")
    )
    staff = User.objects.create(username="staff", email="s@example.com", is_staff=True)
    client.force_login(staff)
    ml = make_link()

    response = client.get(reverse(CHANGELIST))
    assert response.status_code == 200
    assert b'value="unsubscribe"' not in response.content

    run_action(client, ml)
    assert not MagicLinkUnsubscribe.objects.exists()


@pytest.mark.django_db
def test_unsubscribe_list_admin(admin_client):
    url = reverse("admin:magiclink_magiclinkunsubscribe_add")
    response = admin_client.post(url, {"email": "a@example.com"})
    assert response.status_code == 302
    assert MagicLinkUnsubscribe.objects.filter(email="a@example.com").exists()
    assert (
        admin_client.get(
            reverse("admin:magiclink_magiclinkunsubscribe_changelist"), {"q": "a@"}
        )
        .context["cl"]
        .result_count
        == 1
    )
