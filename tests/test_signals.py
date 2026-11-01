from importlib import reload
from time import time

import pytest
from asgiref.sync import sync_to_async
from django.http import HttpRequest
from django.urls import reverse

from magiclink.backends import MagicLinkBackend
from magiclink.forms import sign_load_time
from magiclink.helpers import acreate_magiclink, create_magiclink
from magiclink.models import MagicLink
from magiclink.signals import (
    login_failed,
    login_succeeded,
    magiclink_requested,
    magiclink_sent,
    spam_detected,
)
from magiclink.views import Login, Signup


@pytest.fixture
def receiver(mocker):
    connected = []

    def _connect(signal):
        handler = mocker.Mock()
        signal.connect(handler, weak=False)
        connected.append((signal, handler))
        return handler

    yield _connect

    for signal, handler in connected:
        signal.disconnect(handler)


@pytest.mark.django_db
def test_magiclink_requested(receiver, user):
    handler = receiver(magiclink_requested)
    request = HttpRequest()
    ml = create_magiclink(user.email, request)
    handler.assert_called_once_with(
        signal=magiclink_requested, sender=MagicLink, magiclink=ml, request=request
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_magiclink_requested_async(receiver, user):
    handler = receiver(magiclink_requested)
    request = HttpRequest()
    ml = await acreate_magiclink(user.email, request)
    handler.assert_called_once_with(
        signal=magiclink_requested, sender=MagicLink, magiclink=ml, request=request
    )


@pytest.mark.django_db
def test_magiclink_sent(mocker, rf, receiver, magic_link):
    mocker.patch("magiclink.models.send_mail")
    handler = receiver(magiclink_sent)
    request = rf.get("/")
    ml = magic_link(request)
    ml.send(request)
    handler.assert_called_once_with(
        signal=magiclink_sent, sender=MagicLink, magiclink=ml, request=request
    )


@pytest.mark.django_db
def test_login_succeeded(receiver, user, magic_link):
    handler = receiver(login_succeeded)
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    MagicLinkBackend().authenticate(request=request, token=ml.token, email=user.email)
    handler.assert_called_once_with(
        signal=login_succeeded,
        sender=MagicLinkBackend,
        request=request,
        user=user,
        magiclink=ml,
    )


@pytest.mark.django_db
def test_login_failed_not_found(receiver, user):
    handler = receiver(login_failed)
    request = HttpRequest()
    MagicLinkBackend().authenticate(request=request, token="fake", email=user.email)
    handler.assert_called_once_with(
        signal=login_failed,
        sender=MagicLinkBackend,
        request=request,
        magiclink=None,
        reason="A magic link with that token could not be found",
    )


@pytest.mark.django_db
def test_login_failed_disabled(receiver, user, magic_link):
    handler = receiver(login_failed)
    request = HttpRequest()
    ml = magic_link(request)
    ml.disabled = True
    ml.save()
    MagicLinkBackend().authenticate(request=request, token=ml.token, email=user.email)
    handler.assert_called_once_with(
        signal=login_failed,
        sender=MagicLinkBackend,
        request=request,
        magiclink=ml,
        reason="Magic link is disabled",
    )


@pytest.mark.django_db
def test_login_failed_invalid(receiver, user, magic_link):
    handler = receiver(login_failed)
    request = HttpRequest()
    ml = magic_link(request)
    MagicLinkBackend().authenticate(
        request=request, token=ml.token, email="fake@example.com"
    )
    handler.assert_called_once_with(
        signal=login_failed,
        sender=MagicLinkBackend,
        request=request,
        magiclink=ml,
        reason="Email address does not match",
    )


@pytest.mark.django_db
def test_login_failed_not_sent_without_token(receiver, user):
    handler = receiver(login_failed)
    MagicLinkBackend().authenticate(request=HttpRequest(), token="", email=user.email)
    handler.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_login_succeeded_async(receiver, user, magic_link):
    handler = receiver(login_succeeded)
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    await MagicLinkBackend().aauthenticate(
        request=request, token=ml.token, email=user.email
    )
    handler.assert_called_once_with(
        signal=login_succeeded,
        sender=MagicLinkBackend,
        request=request,
        user=user,
        magiclink=ml,
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_login_failed_async(receiver, user):
    handler = receiver(login_failed)
    request = HttpRequest()
    await MagicLinkBackend().aauthenticate(
        request=request, token="fake", email=user.email
    )
    handler.assert_called_once_with(
        signal=login_failed,
        sender=MagicLinkBackend,
        request=request,
        magiclink=None,
        reason="A magic link with that token could not be found",
    )


@pytest.mark.django_db
def test_spam_detected_login(settings, client, receiver, user, time_machine):
    time_machine.move_to("2000-01-01T00:00:00", tick=False)

    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings

    reload(mlsettings)

    handler = receiver(spam_detected)
    url = reverse("magiclink:login")
    data = {"email": user.email, "load_time": sign_load_time(time())}
    response = client.post(url, data)

    handler.assert_called_once()
    assert handler.call_args.kwargs["sender"] is Login
    assert handler.call_args.kwargs["form"] == response.context["login_form"]


@pytest.mark.django_db
def test_spam_detected_signup(settings, client, receiver):
    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings

    reload(mlsettings)

    handler = receiver(spam_detected)
    url = reverse("magiclink:signup")
    data = {
        "form_name": "SignupFormEmailOnly",
        "email": "test@example.com",
        "url": "test",
        "load_time": sign_load_time(time() - 10),
    }
    client.post(url, data)

    handler.assert_called_once()
    assert handler.call_args.kwargs["sender"] is Signup


@pytest.mark.django_db
def test_spam_detected_not_sent_for_other_errors(settings, client, receiver):
    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings

    reload(mlsettings)

    handler = receiver(spam_detected)
    url = reverse("magiclink:login")
    data = {"email": "not-an-email", "load_time": sign_load_time(time() - 10)}
    client.post(url, data)

    handler.assert_not_called()
