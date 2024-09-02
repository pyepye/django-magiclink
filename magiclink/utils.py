from django.http import HttpRequest
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
import ipaddress
import logging

log = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def anonymize_ip_address(ip_address: str) -> str:
    try:
        parsed_ip = ipaddress.ip_address(ip_address)
    except ValueError as err:
        log.warning(f'Failed to anonymize ip address: {err}')
        return ip_address

    if isinstance(parsed_ip, ipaddress.IPv4Address):
        # Anonymize IPv4 by zeroing out the last octet
        anonymized_ip = ipaddress.IPv4Address(int(parsed_ip) & 0xFFFFFF00)

    elif isinstance(parsed_ip, ipaddress.IPv6Address):
        # Anonymize IPv6 by zeroing out the last 80 bits
        anonymized_ip = ipaddress.IPv6Address(int(parsed_ip) & (0xFFFFFFFFFFFFFFFFFFFF << 80))

    return str(anonymized_ip)

def get_url_path(url: str) -> str:
    """
    url can either be a url name or a url path. First try and reverse a URL,
    if this does not exist then assume it's a url path
    """
    try:
        return reverse(url)
    except NoReverseMatch:
        return url
