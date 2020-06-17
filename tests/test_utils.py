from django.http import HttpRequest

from magiclink.utils import get_client_ip


def test_get_client_ip_http_x_forwarded_for():
    request = HttpRequest()
    ip_addr = '127.0.0.1'
    request.META['HTTP_X_FORWARDED_FOR'] = f'{ip_addr}, 127.0.0.1'
    ip_address = get_client_ip(request)
    assert ip_address == ip_addr


def test_get_client_ip_remote_addr():
    request = HttpRequest()
    remote_addr = '127.0.0.1'
    request.META['REMOTE_ADDR'] = remote_addr
    ip_address = get_client_ip(request)
    assert ip_address == remote_addr
