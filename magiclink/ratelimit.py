from collections.abc import Iterator
from hashlib import sha256
from time import time

from django.core.cache import cache
from django.http import HttpRequest

from . import settings
from .adapter import get_adapter
from .settings import RateLimitRule
from .utils import anonymize_ip


def normalise_email(email: str) -> str:
    local, _, domain = email.strip().lower().rpartition("@")
    return f"{local.split('+', 1)[0]}@{domain}"


def hit(name: str, request: HttpRequest, email: str = "") -> bool:
    """
    Count one event for each rule and return True if any rule is over its limit
    """
    limited = False
    for rule, key in _rule_keys(name, request, email):
        cache.add(key, 0, timeout=rule.seconds)
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=rule.seconds)
            count = 1
        limited = limited or count > rule.limit
    return limited


async def ahit(name: str, request: HttpRequest, email: str = "") -> bool:
    limited = False
    for rule, key in _rule_keys(name, request, email):
        await cache.aadd(key, 0, timeout=rule.seconds)
        try:
            count = await cache.aincr(key)
        except ValueError:
            await cache.aset(key, 1, timeout=rule.seconds)
            count = 1
        limited = limited or count > rule.limit
    return limited


def is_limited(name: str, request: HttpRequest, email: str = "") -> bool:
    """
    Return True if any rule has reached its limit, without counting an event
    """
    return any(
        cache.get(key, 0) >= rule.limit
        for rule, key in _rule_keys(name, request, email)
    )


async def ais_limited(name: str, request: HttpRequest, email: str = "") -> bool:
    for rule, key in _rule_keys(name, request, email):
        if await cache.aget(key, 0) >= rule.limit:
            return True
    return False


def _rule_keys(
    name: str, request: HttpRequest, email: str
) -> Iterator[tuple[RateLimitRule, str]]:
    for rule in settings.RATE_LIMITS.get(name, []):
        value = _rule_value(rule, request, email)
        if value:
            digest = sha256(value.encode()).hexdigest()
            window = int(time()) // rule.seconds
            yield (
                rule,
                (
                    f"magiclink:ratelimit:{name}:{rule.key}:{rule.seconds}:{digest}:{window}"
                ),
            )


def _rule_value(rule: RateLimitRule, request: HttpRequest, email: str) -> str:
    if rule.key == "ip":
        ip = get_adapter().get_client_ip(request)
        return anonymize_ip(ip, ipv4_prefix=32) if ip else ""
    if rule.key == "email":
        return normalise_email(email) if email else ""
    return "site"
