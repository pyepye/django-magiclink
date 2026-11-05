import re
from collections.abc import Callable
from typing import Any, NamedTuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

FORM_NAMES = ("login", "signup")
RATE_LIMIT_NAMES = ("request", "request_site", "verify_failed")
RATE_LIMIT_PERIODS = {"s": 1, "m": 60, "h": 60 * 60, "d": 24 * 60 * 60}
RATE_LIMIT_RULE = re.compile(r"(\d+)/(\d*)([smhd])(?:/(ip|email))?")


class RateLimitRule(NamedTuple):
    limit: int
    seconds: int
    key: str | None


def parse_rate_limit_rules(rules: str) -> list[RateLimitRule]:
    parsed = []
    for rule in filter(None, (part.strip() for part in rules.split(","))):
        match = RATE_LIMIT_RULE.fullmatch(rule)
        seconds = 0
        if match:
            seconds = int(match[2] or 1) * RATE_LIMIT_PERIODS[match[3]]
        if not match or not seconds:
            raise ImproperlyConfigured(
                f'"MAGICLINK_RATE_LIMITS" has an invalid rule: "{rule}"'
            )
        parsed.append(RateLimitRule(int(match[1]), seconds, match[4]))
    return parsed


def _value(name: str, default: object) -> Any:
    return getattr(settings, f"MAGICLINK_{name}", default)


def _boolean(name: str, default: object) -> bool:
    value = _value(name, default)
    if not isinstance(value, bool):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a boolean')
    return value


def _integer(name: str, default: object) -> int:
    try:
        return int(_value(name, default))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be an integer') from None


def _string(name: str, default: object) -> str:
    value = _value(name, default)
    if not isinstance(value, str):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a string')
    return value


def _non_negative_integer(name: str, default: object) -> int:
    value = _integer(name, default)
    if value < 0:
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be 0 or more')
    return value


def _email_styles(name: str, default: object) -> dict[str, str]:
    value = _value(name, default)
    if value and not isinstance(value, dict):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a dict')
    return value


def _antispam_field_time(name: str, default: object) -> float | None:
    value = _value(name, default)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a float') from None


def _honeypot_field(name: str, default: object) -> str:
    value = _value(name, default)
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a non-empty string')
    return value


def _spam_checks(name: str, default: object) -> list[str]:
    value = _value(name, default)
    if not isinstance(value, list | tuple) or not all(
        isinstance(check, str) for check in value
    ):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a list of strings')
    return list(value)


def _email_domains(name: str, default: object) -> list[str]:
    value = _value(name, default)
    if not isinstance(value, list | tuple) or not all(
        isinstance(domain, str) for domain in value
    ):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a list of strings')
    return [domain.lower() for domain in value]


def _rate_limits(name: str, default: object) -> dict[str, list[RateLimitRule]]:
    value = _value(name, default)
    if not isinstance(value, dict):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a dict')
    for limit_name, rules in value.items():
        if limit_name not in RATE_LIMIT_NAMES or not isinstance(rules, str):
            raise ImproperlyConfigured(
                f'"MAGICLINK_{name}" has an invalid entry: "{limit_name}"'
            )
    return {
        limit_name: parse_rate_limit_rules(rules) for limit_name, rules in value.items()
    }


def _forms(name: str, default: object) -> dict[str, str]:
    value = _value(name, default)
    if not isinstance(value, dict):
        raise ImproperlyConfigured(f'"MAGICLINK_{name}" must be a dict')
    for form_name, path in value.items():
        if form_name not in FORM_NAMES or not isinstance(path, str):
            raise ImproperlyConfigured(
                f'"MAGICLINK_{name}" has an invalid entry: "{form_name}"'
            )
    return value


def _site_url(name: str, default: object) -> str:
    value = _string(name, default)
    if value and not value.startswith(("http://", "https://")):
        raise ImproperlyConfigured(
            f'"MAGICLINK_{name}" must start with "http://" or "https://"'
        )
    return value


_SETTINGS: dict[str, tuple[Callable[[str, object], object], object]] = {
    "LOGIN_SENT_REDIRECT": (_value, "magiclink:login_sent"),
    "LOGIN_TEMPLATE_NAME": (_value, "magiclink/login.html"),
    "LOGIN_SENT_TEMPLATE_NAME": (_value, "magiclink/login_sent.html"),
    "LOGIN_FAILED_TEMPLATE_NAME": (_value, "magiclink/login_failed.html"),
    "LOGIN_CONFIRM_TEMPLATE_NAME": (_value, "magiclink/login_confirm.html"),
    # If this has a value the user is redirected to this URL and is not shown
    # LOGIN_FAILED_TEMPLATE_NAME
    "LOGIN_FAILED_REDIRECT": (_value, ""),
    # If this is False a user account is created the first time a user requests
    # a login link
    "REQUIRE_SIGNUP": (_boolean, True),
    "SIGNUP_LOGIN_REDIRECT": (_value, ""),
    "SIGNUP_TEMPLATE_NAME": (_value, "magiclink/signup.html"),
    "TOKEN_LENGTH": (_integer, 50),
    # In seconds
    "AUTH_TIMEOUT": (_integer, 300),
    "TOKEN_USES": (_integer, 1),
    "EMAIL_IGNORE_CASE": (_boolean, True),
    "EMAIL_AS_USERNAME": (_boolean, True),
    "ALLOW_SUPERUSER_LOGIN": (_boolean, True),
    "ALLOW_STAFF_LOGIN": (_boolean, True),
    "IGNORE_IS_ACTIVE_FLAG": (_boolean, False),
    "VERIFY_INCLUDE_EMAIL": (_boolean, True),
    "LOGIN_CONFIRM": (_boolean, False),
    "REQUIRE_SAME_BROWSER": (_boolean, True),
    "REQUIRE_SAME_IP": (_boolean, True),
    "ANONYMIZE_IP": (_boolean, True),
    "TRUSTED_PROXY_COUNT": (_non_negative_integer, 0),
    "TRUSTED_CLIENT_IP_HEADER": (_string, ""),
    "ONE_TOKEN_PER_USER": (_boolean, True),
    # In seconds
    "LOGIN_REQUEST_TIME_LIMIT": (_integer, 30),
    "EMAIL_STYLES": (
        _email_styles,
        {
            "logo_url": "",
            "background_color": "#ffffff",
            "main_text_color": "#000000",
            "button_background_color": "#0078be",
            "button_text_color": "#ffffff",
        },
    ),
    "EMAIL_SUBJECT": (_value, "Your login magic link"),
    "EMAIL_TEMPLATE_NAME_TEXT": (_value, "magiclink/login_email.txt"),
    "EMAIL_TEMPLATE_NAME_HTML": (_value, "magiclink/login_email.html"),
    "PREVENT_ENUMERATION": (_boolean, False),
    "ANTISPAM_FORMS": (_boolean, False),
    "ANTISPAM_FIELD_TIME": (_antispam_field_time, 1),
    # In seconds
    "ANTISPAM_FORM_MAX_AGE": (_integer, 6 * 60 * 60),
    "ANTISPAM_HONEYPOT_FIELD": (_honeypot_field, "url"),
    "ANTISPAM_QUIET_REJECT": (_boolean, False),
    "ADAPTER": (_string, "magiclink.adapter.MagicLinkAdapter"),
    "SPAM_CHECKS": (_spam_checks, []),
    "FORMS": (_forms, {}),
    "ALLOWED_EMAIL_DOMAINS": (_email_domains, []),
    "BLOCKED_EMAIL_DOMAINS": (_email_domains, []),
    "RATE_LIMITS": (_rate_limits, {}),
    "SITE_URL": (_site_url, ""),
    "LOGIN_VERIFY_URL": (_value, "magiclink:login_verify"),
    "UNSUBSCRIBE_LINK": (_boolean, False),
    "UNSUBSCRIBE_TEMPLATE_NAME": (_value, "magiclink/unsubscribe.html"),
    "IGNORE_UNSUBSCRIBE_IF_USER": (_boolean, False),
}


def __getattr__(name: str) -> Any:
    try:
        reader, default = _SETTINGS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    return reader(name, default)


def __dir__() -> list[str]:
    return [*globals(), *_SETTINGS]


def validate() -> None:
    for name in _SETTINGS:
        __getattr__(name)


validate()
