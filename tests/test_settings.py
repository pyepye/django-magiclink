from importlib import reload

import pytest
from django.core.exceptions import ImproperlyConfigured


def test_token_length(settings):
    settings.MAGICLINK_TOKEN_LENGTH = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_token_length_warning(settings):
    settings.MAGICLINK_TOKEN_LENGTH = 1

    with pytest.warns(RuntimeWarning):
        from magiclink import settings
        reload(settings)


def test_email_verify(settings):
    settings.MAGICLINK_EMAIL_VERIFY = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_auth_timeout(settings):
    settings.MAGICLINK_AUTH_TIMEOUT = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_token_uses(settings):
    settings.MAGICLINK_TOKEN_USES = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_email_ignore_case(settings):
    settings.MAGICLINK_EMAIL_IGNORE_CASE = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_require_signup(settings):
    settings.MAGICLINK_REQUIRE_SIGNUP = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_email_as_username(settings):
    settings.MAGICLINK_EMAIL_AS_USERNAME = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_allow_superuser_login(settings):
    settings.MAGICLINK_ALLOW_SUPERUSER_LOGIN = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_allow_staff_login(settings):
    settings.MAGICLINK_ALLOW_STAFF_LOGIN = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_email_with_token(settings):
    settings.MAGICLINK_VERIFY_WITH_EMAIL = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_require_browser(settings):
    settings.MAGICLINK_REQUIRE_BROWSER = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_require_same_ip(settings):
    settings.MAGICLINK_REQUIRE_SAME_IP = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_signup_email_template(settings):
    settings.MAGICLINK_SIGNUP_EMAIL_TEMPLATE = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)


def test_magiclink_email_styles(settings):
    settings.MAGICLINK_EMAIL_STYLES = 'Test'

    with pytest.raises(ImproperlyConfigured):
        from magiclink import settings
        reload(settings)
