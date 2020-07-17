from django.http import HttpRequest

from magiclink.utils import get_client_ip, get_url_path


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


def test_get_url_path_with_name():
    url_name = 'no_login'
    url = get_url_path(url_name)
    assert url == '/no-login/'


def test_get_url_path_with_path():
    url_name = '/test/'
    url = get_url_path(url_name)
    assert url == '/test/'
