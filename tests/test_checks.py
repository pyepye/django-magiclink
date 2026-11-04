import pytest
from django.core.checks import run_checks

from magiclink.adapter import MagicLinkAdapter
from magiclink.checks import check_settings

CACHE_LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CACHE_DUMMY = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
CACHE_DB = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache",
    }
}


class IpAdapter(MagicLinkAdapter):
    def get_client_ip(self, request):
        return "203.0.113.7"


def ids():
    return {message.id for message in check_settings(None)}


@pytest.fixture(autouse=True)
def good_settings(settings):
    settings.ALLOWED_HOSTS = ["example.com"]
    settings.CACHES = CACHE_DB


def test_no_warnings_with_good_settings():
    assert ids() == set()


def test_check_is_registered_with_django(settings):
    settings.ALLOWED_HOSTS = ["*"]
    assert "magiclink.W001" in {m.id for m in run_checks(tags=["security"])}


def test_host_header_warning(settings):
    settings.ALLOWED_HOSTS = ["*"]
    assert ids() == {"magiclink.W001"}


def test_host_header_no_warning_with_site_url(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.MAGICLINK_SITE_URL = "https://example.com"
    assert ids() == set()


def test_host_header_no_warning_with_sites_app(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, "django.contrib.sites"]
    assert ids() == set()


@pytest.mark.parametrize("cache", [CACHE_LOCMEM, CACHE_DUMMY])
def test_rate_limit_cache_warning(settings, cache):
    settings.CACHES = cache
    settings.MAGICLINK_RATE_LIMITS = {"request": "5/h/ip"}
    assert ids() == {"magiclink.W002"}


def test_rate_limit_cache_no_warning_without_limits(settings):
    settings.CACHES = CACHE_LOCMEM
    assert ids() == set()
    settings.MAGICLINK_RATE_LIMITS = {"request": ""}
    assert ids() == set()


def test_rate_limit_cache_no_warning_with_shared_cache(settings):
    settings.MAGICLINK_RATE_LIMITS = {"request": "5/h/ip"}
    assert ids() == set()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SECURE_PROXY_SSL_HEADER", ("HTTP_X_FORWARDED_PROTO", "https")),
        ("USE_X_FORWARDED_HOST", True),
        ("USE_X_FORWARDED_PORT", True),
    ],
)
def test_proxy_warning(settings, name, value):
    setattr(settings, name, value)
    assert ids() == {"magiclink.W003"}


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAGICLINK_TRUSTED_PROXY_COUNT", 1),
        ("MAGICLINK_TRUSTED_CLIENT_IP_HEADER", "X-Real-IP"),
        ("MAGICLINK_ADAPTER", "tests.test_checks.IpAdapter"),
    ],
)
def test_proxy_no_warning_when_client_ip_is_set_up(settings, name, value):
    settings.USE_X_FORWARDED_HOST = True
    setattr(settings, name, value)
    assert ids() == set()


def test_proxy_no_warning_if_ip_is_not_used(settings):
    settings.USE_X_FORWARDED_HOST = True
    settings.MAGICLINK_REQUIRE_SAME_IP = False
    assert ids() == set()


def test_proxy_warning_for_ip_rate_limits_without_same_ip(settings):
    settings.USE_X_FORWARDED_HOST = True
    settings.MAGICLINK_REQUIRE_SAME_IP = False
    settings.MAGICLINK_RATE_LIMITS = {"verify_failed": "10/m/ip"}
    assert ids() == {"magiclink.W003"}


def test_token_length_warning(settings):
    settings.MAGICLINK_TOKEN_LENGTH = 19
    assert ids() == {"magiclink.W004"}
    settings.MAGICLINK_TOKEN_LENGTH = 20
    assert ids() == set()
