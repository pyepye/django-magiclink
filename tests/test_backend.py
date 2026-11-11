import logging

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import aauthenticate, aget_user, alogin
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest

from magiclink.backends import ALREADY_USED, MagicLinkBackend
from magiclink.models import MagicLink
from magiclink.signals import login_failed


@pytest.mark.django_db
def test_auth_backend_get_user(user):
    assert MagicLinkBackend().get_user(user.id)


@pytest.mark.django_db
def test_auth_backend_get_user_do_not_exist(user):
    assert MagicLinkBackend().get_user(123456) is None


@pytest.mark.django_db
def test_auth_backend_get_user_inactive(user):
    user.is_active = False
    user.save()
    assert MagicLinkBackend().get_user(user.id) is None


@pytest.mark.django_db
def test_auth_backend_get_user_inactive_ignore_flag(settings, user):
    settings.MAGICLINK_IGNORE_IS_ACTIVE_FLAG = True

    user.is_active = False
    user.save()
    assert MagicLinkBackend().get_user(user.id) == user


@pytest.mark.django_db
def test_auth_backend(user, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user
    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_auth_backend_no_token(user, magic_link):
    request = HttpRequest()
    user = MagicLinkBackend().authenticate(
        request=request, token="fake", email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_disabled_token(user, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    ml.disabled = True
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_no_email(user, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    user = MagicLinkBackend().authenticate(request=request, token=ml.token)
    assert user is None


@pytest.mark.django_db
def test_auth_backend_invalid(user, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email="fake@email.com"
    )
    assert user is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_auth_backend_aget_user(user):
    assert await MagicLinkBackend().aget_user(user.id) == user


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_auth_backend_aget_user_inactive(user):
    user.is_active = False
    await user.asave()
    assert await MagicLinkBackend().aget_user(user.id) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_and_auser(user, magic_link):
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    request.session = SessionStore()

    authed = await aauthenticate(request, token=ml.token, email=user.email)
    assert authed == user
    assert authed.backend == "magiclink.backends.MagicLinkBackend"

    await alogin(request, authed)
    assert await aget_user(request) == user


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_auth_backend_aget_user_does_not_exist(user):
    assert await MagicLinkBackend().aget_user(123456) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate(user, magic_link):
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    authed = await MagicLinkBackend().aauthenticate(
        request=request, token=ml.token, email=user.email
    )
    assert authed == user
    ml = await MagicLink.objects.aget(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_no_token(user):
    request = HttpRequest()
    authed = await MagicLinkBackend().aauthenticate(
        request=request, token="", email=user.email
    )
    assert authed is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_token_not_found(user):
    request = HttpRequest()
    authed = await MagicLinkBackend().aauthenticate(
        request=request, token="fake", email=user.email
    )
    assert authed is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_disabled_token(user, magic_link):
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    ml.disabled = True
    await ml.asave()
    authed = await MagicLinkBackend().aauthenticate(
        request=request, token=ml.token, email=user.email
    )
    assert authed is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_invalid(user, magic_link):
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    authed = await MagicLinkBackend().aauthenticate(
        request=request, token=ml.token, email="fake@email.com"
    )
    assert authed is None


@pytest.mark.django_db
def test_auth_backend_does_not_log_token(caplog, user):
    caplog.set_level(logging.DEBUG, logger="magiclink")
    MagicLinkBackend().authenticate(
        request=HttpRequest(), token="secret-token", email=user.email
    )
    assert "secret-token" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_does_not_log_token(caplog, user):
    caplog.set_level(logging.DEBUG, logger="magiclink")
    await MagicLinkBackend().aauthenticate(
        request=HttpRequest(), token="secret-token", email=user.email
    )
    assert "secret-token" not in caplog.text


def link_used_by_other_request_during(method):
    def validate_then_other_request_uses_link(self, *args, **kwargs):
        user = method(self, *args, **kwargs)
        assert MagicLink.objects.get(pk=self.pk).used()
        return user

    return validate_then_other_request_uses_link


@pytest.mark.django_db
def test_auth_backend_fails_if_link_used_by_another_request(mocker, user, magic_link):
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    mocker.patch.object(
        MagicLink, "validate", link_used_by_other_request_during(MagicLink.validate)
    )
    receiver = mocker.Mock()
    login_failed.connect(receiver)
    try:
        authed = MagicLinkBackend().authenticate(
            request=request, token=ml.token, email=user.email
        )
    finally:
        login_failed.disconnect(receiver)

    assert authed is None
    assert receiver.call_args.kwargs["reason"] == ALREADY_USED
    ml.refresh_from_db()
    assert ml.times_used == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aauthenticate_fails_if_link_used_by_another_request(
    mocker, user, magic_link
):
    request = HttpRequest()
    ml = await sync_to_async(magic_link)(request)
    request.COOKIES[f"magiclink{ml.pk}"] = ml.cookie_value
    avalidate = MagicLink.avalidate

    async def avalidate_then_other_request_uses_link(self, *args, **kwargs):
        user = await avalidate(self, *args, **kwargs)
        assert await (await MagicLink.objects.aget(pk=self.pk)).aused()
        return user

    mocker.patch.object(MagicLink, "avalidate", avalidate_then_other_request_uses_link)
    receiver = mocker.Mock()
    login_failed.connect(receiver)
    try:
        authed = await MagicLinkBackend().aauthenticate(
            request=request, token=ml.token, email=user.email
        )
    finally:
        login_failed.disconnect(receiver)

    assert authed is None
    assert receiver.call_args.kwargs["reason"] == ALREADY_USED
    await ml.arefresh_from_db()
    assert ml.times_used == 1
