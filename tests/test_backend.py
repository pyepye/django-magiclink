import pytest
from django.http import HttpRequest

from magiclink.backends import MagicLinkBackend
from magiclink.models import MagicLink

from .fixtures import magic_link, user  # NOQA: F401


@pytest.mark.django_db
def test_auth_backend_get_user(user):  # NOQA: F811
    assert MagicLinkBackend().get_user(user.id)


@pytest.mark.django_db
def test_auth_backend_get_user_do_not_exist(user):  # NOQA: F811
    assert MagicLinkBackend().get_user(123456) is None


@pytest.mark.django_db
def test_auth_backend(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user
    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_auth_backend_no_token(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    user = MagicLinkBackend().authenticate(
        request=request, token='fake', email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_disabled_token(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml.disabled = True
    ml.save()
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email=user.email
    )
    assert user is None


@pytest.mark.django_db
def test_auth_backend_no_email(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    user = MagicLinkBackend().authenticate(request=request, token=ml.token)
    assert user is None


@pytest.mark.django_db
def test_auth_backend_invalid(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    user = MagicLinkBackend().authenticate(
        request=request, token=ml.token, email='fake@email.com'
    )
    assert user is None
