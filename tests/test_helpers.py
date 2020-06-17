from importlib import reload
from datetime import timedelta

import pytest
from django.http import HttpRequest
from django.utils import timezone

from magiclink.helpers import create_magiclink
from magiclink import settings as mlsettings

from .fixtures import user  # NOQA: F401


@pytest.mark.django_db
def test_create_magiclink(settings, freezer):
    freezer.move_to('2000-01-01T00:00:00')

    email = 'test@example.com'
    remote_addr = '127.0.0.1'
    expiry = timezone.now() + timedelta(seconds=mlsettings.AUTH_TIMEOUT)
    request = HttpRequest()
    request.META['REMOTE_ADDR'] = remote_addr
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email
    assert len(magic_link.token) == mlsettings.AUTH_TIMEOUT
    assert magic_link.expiry == expiry
    assert magic_link.redirect_url == settings.LOGIN_REDIRECT_URL
    assert len(magic_link.cookie_value) == 36
    assert magic_link.ip_address == remote_addr


@pytest.mark.django_db
def test_create_magiclink_redirect_url(settings, freezer):
    email = 'test@example.com'
    request = HttpRequest()
    redirect_url = '/test/'
    magic_link = create_magiclink(email, request, redirect_url=redirect_url)
    assert magic_link.email == email
    assert magic_link.redirect_url == redirect_url


@pytest.mark.django_db
def test_create_magiclink_email_ignore_case(settings, freezer):
    email = 'TEST@example.com'
    request = HttpRequest()
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email.lower()


@pytest.mark.django_db
def test_create_magiclink_email_ignore_case_off(settings, freezer):
    settings.MAGICLINK_EMAIL_IGNORE_CASE = False
    from magiclink import settings
    reload(settings)

    email = 'TEST@example.com'
    request = HttpRequest()
    magic_link = create_magiclink(email, request)
    assert magic_link.email == email
