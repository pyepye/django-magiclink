from django.conf import settings as django_settings
from django.http import HttpRequest
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme

from . import settings


def get_client_ip(request: HttpRequest) -> str | None:
    if settings.TRUSTED_CLIENT_IP_HEADER:
        ip = request.headers.get(settings.TRUSTED_CLIENT_IP_HEADER, "").strip()
        if ip:
            return ip

    if settings.TRUSTED_PROXY_COUNT:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
        if len(ips) >= settings.TRUSTED_PROXY_COUNT:
            return ips[-settings.TRUSTED_PROXY_COUNT]

    return request.META.get("REMOTE_ADDR")


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
