from importlib import reload
from urllib.parse import urlencode

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.http.cookie import SimpleCookie
from django.urls import reverse

from magiclink.models import MagicLink

from .fixtures import magic_link, user  # NOQA: F401

User = get_user_model()


def test_login_page_get(client):
    url = reverse('magiclink:login')
    response = client.get(url)
    assert response.context_data['login_form']
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_post(mocker, client, user, settings):  # NOQA: F811
    send_mail = mocker.patch('magiclink.models.send_mail')

    url = reverse('magiclink:login')
    data = {'email': user.email}
    response = client.post(url, data)
    assert response.status_code == 302
    usr = User.objects.get(email=user.email)
    assert usr
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink

    from magiclink import settings as mlsettings
    send_mail.assert_called_once_with(
        subject=mlsettings.EMAIL_SUBJECT,
        message=mocker.ANY,
        recipient_list=[user.email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        html_message=mocker.ANY,
    )


@pytest.mark.django_db
def test_login_post_no_user(client):
    url = reverse('magiclink:login')
    data = {'email': 'fake@example.com'}
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['We could not find a user with that email address']
    assert response.context_data['login_form'].errors['email'] == error


@pytest.mark.django_db
def test_login_email_wrong_case(settings, client, user):  # NOQA: F811
    settings.MAGICLINK_EMAIL_IGNORE_CASE = False
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email.upper()}
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['We could not find a user with that email address']
    assert response.context_data['login_form'].errors['email'] == error


@pytest.mark.django_db
def test_login_email_ignore_case(settings, client, user):  # NOQA: F811
    settings.MAGICLINK_EMAIL_IGNORE_CASE = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email.upper()}
    response = client.post(url, data)
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink
    assert response.status_code == 302


@pytest.mark.django_db
def test_login_post_no_user_require_signup_false(settings, client):
    settings.MAGICLINK_REQUIRE_SIGNUP = False
    from magiclink import settings as mlsettings
    reload(mlsettings)

    email = 'fake@example.com'
    url = reverse('magiclink:login')
    data = {'email': email}
    response = client.post(url, data)
    assert response.status_code == 302
    usr = User.objects.get(email=email)
    assert usr
    magiclink = MagicLink.objects.get(email=email)
    assert magiclink


@pytest.mark.django_db
def test_login_post_invalid(client, user):  # NOQA: F811
    url = reverse('magiclink:login')
    data = {'email': 'notanemail'}
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['Enter a valid email address.']
    assert response.context_data['login_form'].errors['email'] == error


@pytest.mark.django_db
def test_login_verify(client, settings, user, magic_link):  # NOQA: F811
    url = reverse('magiclink:login_verify')
    request = HttpRequest()
    ml = magic_link(request)
    ml.ip_address = '127.0.0.1'  # This is a little hacky
    ml.save()

    params = {'token': ml.token}
    params['email'] = ml.email
    query = urlencode(params)
    url = f'{url}?{query}'

    client.cookies = SimpleCookie({'magiclink': ml.cookie_value})
    response = client.get(url)
    assert response.status_code == 302

    needs_login_url = reverse('needs_login')
    needs_login_response = client.get(needs_login_url)
    assert needs_login_response.status_code == 200


@pytest.mark.django_db
def test_login_verify_authentication_fail(client, settings, user, magic_link):  # NOQA: F811
    url = reverse('magiclink:login_verify')
    request = HttpRequest()
    ml = magic_link(request)
    ml.ip_address = '127.0.0.1'  # This is a little hacky
    ml.save()

    params = {'token': ml.token}
    query = urlencode(params)
    url = f'{url}?{query}'

    client.cookies = SimpleCookie({'magiclink': ml.cookie_value})
    response = client.get(url)
    assert response.status_code == 404



@pytest.mark.django_db
def test_login_verify_no_token(client):
    url = reverse('magiclink:login_verify')
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_logout(client, user):  # NOQA: F811
    client.force_login(user)
    url = reverse('magiclink:logout')
    response = client.get(url)
    assert response.status_code == 302

    needs_login_url = reverse('needs_login')
    needs_login_response = client.get(needs_login_url)
    assert needs_login_response.status_code == 302
