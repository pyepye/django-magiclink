from datetime import timedelta
from importlib import reload

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from magiclink import settings as mlsettings
from magiclink.helpers import create_magiclink, get_or_create_user
from magiclink.models import MagicLink, MagicLinkError

from .fixtures import user  # NOQA: F401
from .models import CustomUserEmailOnly, CustomUserFullName, CustomUserName

User = get_user_model()


@pytest.mark.django_db
def test_create_magiclink(settings, freezer):
    freezer.move_to('2000-01-01T00:00:00')

    email = 'test@example.com'
    expiry = timezone.now() + timedelta(seconds=mlsettings.AUTH_TIMEOUT)
    request = HttpRequest()
    request.META['REMOTE_ADDR'] = '127.0.0.1'
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email
    assert len(magic_link.token) == mlsettings.TOKEN_LENGTH
    assert magic_link.expiry == expiry
    assert magic_link.redirect_url == reverse(settings.LOGIN_REDIRECT_URL)
    assert len(magic_link.cookie_value) == 36
    assert magic_link.ip_address == '127.0.0.0'  # Anonymize IP by default

@pytest.mark.django_db
def test_create_magiclink_ipv6_remote_addr(settings, freezer):
    freezer.move_to('2000-01-01T00:00:00')

    email = 'test@example.com'
    expiry = timezone.now() + timedelta(seconds=mlsettings.AUTH_TIMEOUT)
    request = HttpRequest()
    request.META['REMOTE_ADDR'] = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email
    assert len(magic_link.token) == mlsettings.TOKEN_LENGTH
    assert magic_link.expiry == expiry
    assert magic_link.redirect_url == reverse(settings.LOGIN_REDIRECT_URL)
    assert len(magic_link.cookie_value) == 36
    assert magic_link.ip_address == '2001:db8:85a3::'  # Anonymize IP by default


@pytest.mark.django_db
def test_create_magiclink_require_same_ip_off_no_ip(settings):
    settings.MAGICLINK_REQUIRE_SAME_IP = False
    from magiclink import settings as mlsettings
    reload(mlsettings)

    request = HttpRequest()
    request.META['REMOTE_ADDR'] = '127.0.0.1'
    magic_link = create_magiclink('test@example.com', request)
    assert magic_link.ip_address is None


@pytest.mark.django_db
def test_create_magiclink_none_anonymized_ip(settings):
    settings.MAGICLINK_ANONYMIZE_IP = False
    from magiclink import settings as mlsettings
    reload(mlsettings)

    request = HttpRequest()
    ip_address = '127.0.0.1'
    request.META['REMOTE_ADDR'] = ip_address
    magic_link = create_magiclink('test@example.com', request)
    assert magic_link.ip_address == ip_address


@pytest.mark.django_db
def test_create_magiclink_redirect_url():
    email = 'test@example.com'
    request = HttpRequest()
    redirect_url = '/test/'
    magic_link = create_magiclink(email, request, redirect_url=redirect_url)
    assert magic_link.email == email
    assert magic_link.redirect_url == redirect_url


@pytest.mark.django_db
def test_create_magiclink_email_ignore_case():
    email = 'TEST@example.com'
    request = HttpRequest()
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email.lower()


@pytest.mark.django_db
def test_create_magiclink_email_ignore_case_off(settings):
    settings.MAGICLINK_EMAIL_IGNORE_CASE = False
    from magiclink import settings
    reload(settings)

    email = 'TEST@example.com'
    request = HttpRequest()
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email


@pytest.mark.django_db
def test_create_magiclink_one_token_per_user(freezer):
    email = 'test@example.com'
    request = HttpRequest()
    freezer.move_to('2000-01-01T00:00:00')
    magic_link = create_magiclink(email, request)
    assert magic_link.disabled is False

    freezer.move_to('2000-01-01T00:00:31')
    create_magiclink(email, request)

    magic_link = MagicLink.objects.get(token=magic_link.token)
    assert magic_link.disabled is True
    assert magic_link.email == email


@pytest.mark.django_db
def test_create_magiclink_login_request_time_limit():
    email = 'test@example.com'
    request = HttpRequest()
    create_magiclink(email, request)
    with pytest.raises(MagicLinkError):
        create_magiclink(email, request)


@pytest.mark.django_db
def test_get_or_create_user_exists(user):  # NOQA: F811
    usr = get_or_create_user(email=user.email)
    assert usr == user
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_get_or_create_user_exists_ignore_case(settings, user):  # NOQA: F811
    settings.MAGICLINK_EMAIL_IGNORE_CASE = True
    from magiclink import settings
    reload(settings)

    usr = get_or_create_user(email=user.email.upper())
    assert usr == user
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_get_or_create_user_email_as_username():
    email = 'test@example.com'
    usr = get_or_create_user(email=email)
    assert usr.email == email
    assert usr.username == email


@pytest.mark.django_db
def test_get_or_create_user_random_username(settings):
    settings.MAGICLINK_EMAIL_AS_USERNAME = False
    from magiclink import settings
    reload(settings)

    email = 'test@example.com'
    usr = get_or_create_user(email=email)
    assert usr.email == email
    assert usr.username != email
    assert len(usr.username) == 10


@pytest.mark.django_db
def test_get_or_create_user_first_name():
    first_name = 'fname'
    usr = get_or_create_user(email='test@example.com', first_name=first_name)
    assert usr.first_name == first_name


@pytest.mark.django_db
def test_get_or_create_user_last_name():
    last_name = 'lname'
    usr = get_or_create_user(email='test@example.com', last_name=last_name)
    assert usr.last_name == last_name


@pytest.mark.django_db
def test_get_or_create_user_no_username(mocker):
    gum = mocker.patch('magiclink.helpers.get_user_model')
    gum.return_value = CustomUserEmailOnly

    from magiclink.helpers import get_or_create_user
    email = 'test@example.com'
    usr = get_or_create_user(email=email)
    assert usr.email == email


@pytest.mark.django_db
def test_get_or_create_user_full_name(mocker):
    gum = mocker.patch('magiclink.helpers.get_user_model')
    gum.return_value = CustomUserFullName

    from magiclink.helpers import get_or_create_user
    email = 'test@example.com'
    first = 'fname'
    last = 'lname'
    usr = get_or_create_user(email=email, first_name=first, last_name=last)
    assert usr.email == email
    assert usr.full_name == f'{first} {last}'


@pytest.mark.django_db
def test_get_or_create_user_name(mocker):
    gum = mocker.patch('magiclink.helpers.get_user_model')
    gum.return_value = CustomUserName

    from magiclink.helpers import get_or_create_user
    email = 'test@example.com'
    first = 'fname'
    last = 'lname'
    usr = get_or_create_user(email=email, first_name=first, last_name=last)
    assert usr.email == email
    assert usr.name == f'{first} {last}'
