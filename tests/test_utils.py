from importlib import reload

from django.http import HttpRequest

from magiclink.utils import get_client_ip, get_url_path


def test_get_client_ip_ignores_x_forwarded_for():
    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4"
    assert get_client_ip(request) == "10.0.0.1"


def test_get_client_ip_trusted_proxy_count(settings):
    settings.MAGICLINK_TRUSTED_PROXY_COUNT = 1
    from magiclink import settings as mlsettings

    reload(mlsettings)

    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8"
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_trusted_proxy_count_two(settings):
    settings.MAGICLINK_TRUSTED_PROXY_COUNT = 2
    from magiclink import settings as mlsettings

    reload(mlsettings)

    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8, 10.0.0.2"
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_too_few_forwarded_ips(settings):
    settings.MAGICLINK_TRUSTED_PROXY_COUNT = 2
    from magiclink import settings as mlsettings

    reload(mlsettings)

    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "5.6.7.8"
    assert get_client_ip(request) == "10.0.0.1"


def test_get_client_ip_trusted_header(settings):
    settings.MAGICLINK_TRUSTED_CLIENT_IP_HEADER = "X-Real-IP"
    from magiclink import settings as mlsettings

    reload(mlsettings)

    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_REAL_IP"] = "5.6.7.8"
    assert get_client_ip(request) == "5.6.7.8"


def test_get_client_ip_trusted_header_missing(settings):
    settings.MAGICLINK_TRUSTED_CLIENT_IP_HEADER = "X-Real-IP"
    from magiclink import settings as mlsettings

    reload(mlsettings)

    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    assert get_client_ip(request) == "10.0.0.1"


def test_get_client_ip_remote_addr():
    request = HttpRequest()
    remote_addr = "127.0.0.1"
    request.META["REMOTE_ADDR"] = remote_addr
    ip_address = get_client_ip(request)
    assert ip_address == remote_addr


def test_get_url_path_with_name():
    url_name = "no_login"
    url = get_url_path(url_name)
    assert url == "/no-login/"


def test_get_url_path_with_path():
    url_name = "/test/"
    url = get_url_path(url_name)
    assert url == "/test/"
