import ipaddress
import logging
from functools import cache

from django.conf import settings as django_settings
from django.http import HttpRequest
from django.http.request import split_domain_port
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme

from . import settings

log = logging.getLogger(__name__)


def clean_ip(value: str) -> str | None:
    """
    Return the IP address in value without a port, or None if it is not valid
    """
    value = value.strip()
    host, _ = split_domain_port(value)
    try:
        return str(ipaddress.ip_address(host.strip("[]") or value)).split("%")[0]
    except ValueError:
        return None


@cache
def warn_once(message: str) -> None:
    log.warning(message)


def get_client_ip(request: HttpRequest) -> str | None:
    if (
        not settings.TRUSTED_CLIENT_IP_HEADER
        and not settings.TRUSTED_PROXY_COUNT
        and request.META.get("HTTP_X_FORWARDED_FOR")
    ):
        warn_once(
            "X-Forwarded-For is ignored, so the client IP address comes from "
            "REMOTE_ADDR. If Django runs behind a proxy or load balancer, set "
            "MAGICLINK_TRUSTED_PROXY_COUNT or MAGICLINK_TRUSTED_CLIENT_IP_HEADER"
        )

    ip = None
    if settings.TRUSTED_CLIENT_IP_HEADER:
        ip = clean_ip(request.headers.get(settings.TRUSTED_CLIENT_IP_HEADER, ""))

    if not ip and settings.TRUSTED_PROXY_COUNT:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ips = [value for value in x_forwarded_for.split(",") if value.strip()]
        if len(ips) >= settings.TRUSTED_PROXY_COUNT:
            ip = clean_ip(ips[-settings.TRUSTED_PROXY_COUNT])

    ip = ip or clean_ip(request.META.get("REMOTE_ADDR", ""))
    if not ip:
        log.warning(
            "Could not find the client IP address. If Django runs behind a proxy, set "
            "MAGICLINK_TRUSTED_PROXY_COUNT or MAGICLINK_TRUSTED_CLIENT_IP_HEADER"
        )
    return ip


def anonymize_ip(ip: str, ipv4_prefix: int = 24) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip

    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    prefix = ipv4_prefix if address.version == 4 else 64
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network.network_address)


def email_domain_allowed(email: str) -> bool:
    """
    Check the domain of an email address and its parent domains against the
    allowed and blocked lists
    """
    parts = email.rpartition("@")[2].lower().split(".")
    domains = {".".join(parts[index:]) for index in range(len(parts))}
    if domains.intersection(settings.BLOCKED_EMAIL_DOMAINS):
        return False
    allowed = settings.ALLOWED_EMAIL_DOMAINS
    return not allowed or bool(domains.intersection(allowed))


def get_url_path(url: str) -> str:
    """
    url can either be a url name or a url path. First try and reverse a URL,
    if this does not exist then assume it's a url path
    """
    try:
        return reverse(url)
    except NoReverseMatch:
        return url


def get_safe_redirect_url(request: HttpRequest, url: str) -> str:
    """
    Return url if it points to an allowed host, otherwise an empty string
    """
    allowed_hosts = django_settings.ALLOWED_HOSTS
    if "*" in allowed_hosts:
        allowed_hosts = [request.get_host()]
    url_is_safe = url_has_allowed_host_and_scheme(
        url=url,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure(),
    )
    return url if url_is_safe else ""
