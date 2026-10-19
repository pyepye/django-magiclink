import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import aauthenticate, aget_user, alogin
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest

from magiclink.backends import MagicLinkBackend
from magiclink.models import MagicLink


@pytest.mark.django_db
def test_auth_backend_get_user(user):
    assert MagicLinkBackend().get_user(user.id)


@pytest.mark.django_db
def test_auth_backend_get_user_do_not_exist(user):
    assert MagicLinkBackend().get_user(123456) is None


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
