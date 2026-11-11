from django.apps import apps
from django.conf import settings as django_settings
from django.core.cache import caches
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.checks import CheckMessage, Warning

from . import settings
from .adapter import MagicLinkAdapter, get_adapter


def check_settings(app_configs, **kwargs) -> list[CheckMessage]:
    return [
        *_check_host_header(),
        *_check_rate_limit_cache(),
        *_check_proxy(),
        *_check_token_length(),
    ]


def _check_host_header() -> list[CheckMessage]:
    if (
        "*" not in django_settings.ALLOWED_HOSTS
        or settings.SITE_URL
        or apps.is_installed("django.contrib.sites")
    ):
        return []
    return [
        Warning(
            'ALLOWED_HOSTS is ["*"], so the link in the login email can point to '
            "another site.",
            hint="Set MAGICLINK_SITE_URL, or set ALLOWED_HOSTS to your domains.",
            id="magiclink.W001",
        )
    ]


def _check_rate_limit_cache() -> list[CheckMessage]:
    if not any(settings.RATE_LIMITS.values()):
        return []
    if not isinstance(caches["default"], LocMemCache | DummyCache):
        return []
    return [
        Warning(
            "MAGICLINK_RATE_LIMITS is set, but the default cache is not shared "
            "by all workers.",
            hint="Use a shared cache such as Redis, Memcached or the database.",
            id="magiclink.W002",
        )
    ]


def _check_proxy() -> list[CheckMessage]:
    behind_proxy = (
        django_settings.SECURE_PROXY_SSL_HEADER
        or django_settings.USE_X_FORWARDED_HOST
        or django_settings.USE_X_FORWARDED_PORT
    )
    uses_ip = settings.REQUIRE_SAME_IP or any(
        rule.key == "ip" for rules in settings.RATE_LIMITS.values() for rule in rules
    )
    if (
        not behind_proxy
        or not uses_ip
        or settings.TRUSTED_PROXY_COUNT
        or settings.TRUSTED_CLIENT_IP_HEADER
        or type(get_adapter()).get_client_ip is not MagicLinkAdapter.get_client_ip
    ):
        return []
    return [
        Warning(
            "Django appears to be behind a proxy, but the client IP address comes "
            "from REMOTE_ADDR, which is the address of the proxy.",
            hint=(
                "Set MAGICLINK_TRUSTED_PROXY_COUNT or "
                "MAGICLINK_TRUSTED_CLIENT_IP_HEADER."
            ),
            id="magiclink.W003",
        )
    ]


def _check_token_length() -> list[CheckMessage]:
    if settings.TOKEN_LENGTH >= 20:
        return []
    return [
        Warning(
            "Shorter MAGICLINK_TOKEN_LENGTH values make your login more susceptible "
            "to brute force attacks.",
            hint="Set MAGICLINK_TOKEN_LENGTH to 20 or more.",
            id="magiclink.W004",
        )
    ]
