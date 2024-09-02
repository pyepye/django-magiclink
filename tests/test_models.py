from datetime import timedelta
from importlib import reload
from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from magiclink import settings
from magiclink.models import MagicLink, MagicLinkError, MagicLinkUnsubscribe

from .fixtures import magic_link, user  # NOQA: F401

User = get_user_model()


@pytest.mark.django_db
def test_model_string(magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    assert str(ml) == f'{ml.email} - {ml.expiry}'


@pytest.mark.django_db
def test_generate_url(settings, magic_link):  # NOQA: F811
    settings.MAGICLINK_LOGIN_VERIFY_URL = 'magiclink:login_verify'
    from magiclink import settings
    reload(settings)

    request = HttpRequest()
    host = '127.0.0.1'
    login_url = reverse('magiclink:login_verify')
    request.META['SERVER_NAME'] = host
    request.META['SERVER_PORT'] = 80
    ml = magic_link(request)
    url = f'http://{host}{login_url}?token={ml.token}&email={quote(ml.email)}'
    assert ml.generate_url(request) == url


@pytest.mark.django_db
def test_generate_url_custom_verify(settings, magic_link):  # NOQA: F811
    settings.MAGICLINK_LOGIN_VERIFY_URL = 'custom_login_verify'
    from magiclink import settings
    reload(settings)

    request = HttpRequest()
    host = '127.0.0.1'
    login_url = reverse('custom_login_verify')
    request.META['SERVER_NAME'] = host
    request.META['SERVER_PORT'] = 80
    ml = magic_link(request)
    url = f'http://{host}{login_url}?token={ml.token}&email={quote(ml.email)}'
    assert ml.generate_url(request) == url

    settings.MAGICLINK_LOGIN_VERIFY_URL = 'magiclink:login_verify'
    from magiclink import settings
    reload(settings)


@pytest.mark.django_db
def test_send_email(mocker, settings, magic_link):  # NOQA: F811
    from magiclink import settings as mlsettings
    send_mail = mocker.patch('magiclink.models.send_mail')
    render_to_string = mocker.patch('magiclink.models.render_to_string')

    request = HttpRequest()
    request.META['SERVER_NAME'] = '127.0.0.1'
    request.META['SERVER_PORT'] = 80

    ml = magic_link(request)
    ml.send(request)

    usr = User.objects.get(email=ml.email)
    context = {
        'subject': mlsettings.EMAIL_SUBJECT,
        'user': usr,
        'magiclink': ml.generate_url(request),
        'expiry': ml.expiry,
        'ip_address': ml.ip_address,
        'created': ml.created,
        'require_same_ip': mlsettings.REQUIRE_SAME_IP,
        'require_same_browser': mlsettings.REQUIRE_SAME_BROWSER,
        'token_uses': mlsettings.TOKEN_USES,
        'style': mlsettings.EMAIL_STYLES,
    }
    render_to_string.assert_has_calls([
        mocker.call(mlsettings.EMAIL_TEMPLATE_NAME_TEXT, context),
        mocker.call(mlsettings.EMAIL_TEMPLATE_NAME_HTML, context),
    ])
    send_mail.assert_called_once_with(
        subject=mlsettings.EMAIL_SUBJECT,
        message=mocker.ANY,
        recipient_list=[ml.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        html_message=mocker.ANY,
    )


@pytest.mark.django_db
def test_send_email_error_email_in_unsubscribe(magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    MagicLinkUnsubscribe.objects.create(email=ml.email)

    with pytest.raises(MagicLinkError) as error:
        ml.send(request)

    error.match('Email address is on the unsubscribe list')


@pytest.mark.django_db
def test_send_email_pass_email_in_unsubscribe(mocker, settings, magic_link):  # NOQA: E501, F811
    settings.MAGICLINK_IGNORE_UNSUBSCRIBE_IF_USER = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    send_mail = mocker.patch('magiclink.models.send_mail')

    request = HttpRequest()
    request.META['SERVER_NAME'] = '127.0.0.1'
    request.META['SERVER_PORT'] = 80
    ml = magic_link(request)
    MagicLinkUnsubscribe.objects.create(email=ml.email)

    ml.send(request)

    send_mail.assert_called_once_with(
        subject=mlsettings.EMAIL_SUBJECT,
        message=mocker.ANY,
        recipient_list=[ml.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        html_message=mocker.ANY,
    )


@pytest.mark.django_db
def test_validate(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml_user = ml.validate(request=request, email=user.email)
    assert ml_user == user


@pytest.mark.django_db
def test_validate_email_ignore_case(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml_user = ml.validate(request=request, email=user.email.upper())
    assert ml_user == user


@pytest.mark.django_db
def test_validate_wrong_email(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    email = 'fake@email.com'
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=email)

    error.match('Email address does not match')


@pytest.mark.django_db
def test_validate_expired(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml.expiry = timezone.now() - timedelta(seconds=1)
    ml.save()

    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('Magic link has expired')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_validate_wrong_ip(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml.ip_address = '255.255.255.255'
    ml.save()
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('IP address is different from the IP address used to request '
                'the magic link')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_validate_ipv6_anonymization(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    request.META['REMOTE_ADDR'] = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'

    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml.ip_address = '2001:db8:85a3::'
    ml.save()

    ml_user = ml.validate(request=request, email=user.email.upper())
    assert ml_user == user


@pytest.mark.django_db
def test_validate_different_browser(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = 'bad_value'
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('Browser is different from the browser used to request the '
                'magic link')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_validate_used_times(user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    ml.times_used = settings.TOKEN_USES
    ml.save()
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('Magic link has been used too many times')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == settings.TOKEN_USES + 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_validate_superuser(settings, user, magic_link):  # NOQA: F811
    settings.MAGICLINK_ALLOW_SUPERUSER_LOGIN = False
    from magiclink import settings
    reload(settings)

    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    user.is_superuser = True
    user.save()
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('You can not login to a super user account using a magic link')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True


@pytest.mark.django_db
def test_validate_staff(settings, user, magic_link):  # NOQA: F811
    settings.MAGICLINK_ALLOW_STAFF_LOGIN = False
    from magiclink import settings
    reload(settings)

    request = HttpRequest()
    ml = magic_link(request)
    request.COOKIES[f'magiclink{ml.pk}'] = ml.cookie_value
    user.is_staff = True
    user.save()
    with pytest.raises(MagicLinkError) as error:
        ml.validate(request=request, email=user.email)

    error.match('You can not login to a staff account using a magic link')

    ml = MagicLink.objects.get(token=ml.token)
    assert ml.times_used == 1
    assert ml.disabled is True
