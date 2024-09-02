from django.http import HttpRequest

from magiclink.utils import get_client_ip, get_url_path, anonymize_ip_address


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

def test_anonymize_ip_address_ipv4():
    ipv4 = '127.0.0.1'
    anonymized_ipv4 = anonymize_ip_address(ipv4)
    assert anonymized_ipv4 == '127.0.0.0' # last octet zeroed


def test_anonymize_ip_address_ipv6():
    ipv6 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
    anonymized_ipv6 = anonymize_ip_address(ipv6)
    assert anonymized_ipv6 == '2001:db8:85a3::' # last 80 bits (SLA ID + Interface ID) zeroed

def test_anonymize_ip_address_invalid_value():
    bad_input = '127'
    result = anonymize_ip_address(bad_input)
    assert result == bad_input # returns original input
