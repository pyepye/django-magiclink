from importlib import reload
from datetime import timedelta
import pytest
from django.http import HttpRequest
from django.utils import timezone

from magiclink.backends import MagicLinkBackend
from magiclink import settings

from .fixtures import user, magic_link  # NOQA: F401


@pytest.mark.django_db
def test_auth_backend(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user


@pytest.mark.django_db
def test_auth_backend_email_ignore_case(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email.upper()
    )
    assert user


@pytest.mark.django_db
def test_auth_backend_no_token(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user = MagicLinkBackend().authenticate(
        request=request, token='fake', email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_disabled_token(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    ml.disabled = True
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_no_email(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user = MagicLinkBackend().authenticate(request=request, token=ml.token)
    assert user is None


@pytest.mark.django_db
def test_auth_backend_wrong_email(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email='fake@email.com'
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_expired(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    ml.expiry = timezone.now() - timedelta(seconds=1)
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_expired(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    ml.ip_address = '255.255.255.255'
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_used_times(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    ml.times_used = settings.TOKEN_USES
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_superuser(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user.is_superuser = True
    user.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_staff(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    user.is_staff = True
    user.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None
