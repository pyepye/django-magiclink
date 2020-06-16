from importlib import reload

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from magiclink.models import MagicLink

from .fixtures import user  # NOQA: F401

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
    magic_link = MagicLink.objects.get(email=user.email)
    assert magic_link

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
    magic_link = MagicLink.objects.get(email=email)
    assert magic_link


@pytest.mark.django_db
def test_login_post_invalid(client, user):  # NOQA: F811
    url = reverse('magiclink:login')
    data = {'email': 'notanemail'}
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['Enter a valid email address.']
    assert response.context_data['login_form'].errors['email'] == error
