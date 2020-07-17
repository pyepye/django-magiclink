import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from magiclink.models import MagicLink

User = get_user_model()


def test_signup_get(client):
    url = reverse('magiclink:signup')
    response = client.get(url)
    assert response.context_data['SignupForm']
    assert response.context_data['SignupFormEmailOnly']
    assert response.context_data['SignupFormWithUsername']
    assert response.context_data['SignupFormFull']
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_post(mocker, client, settings):  # NOQA: F811
    from magiclink import settings as mlsettings
    send_mail = mocker.patch('magiclink.models.send_mail')

    url = reverse('magiclink:signup')
    email = 'test@example.com'
    data = {
        'form_name': 'SignupForm',
        'email': email,
        'name': 'testname',
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')

    usr = User.objects.get(email=email)
    assert usr
    magic_link = MagicLink.objects.get(email=email)
    assert magic_link

    send_mail.assert_called_once_with(
        subject=mlsettings.EMAIL_SUBJECT,
        message=mocker.ANY,
        recipient_list=[email],
        from_email=settings.DEFAULT_FROM_EMAIL,
        html_message=mocker.ANY,
    )


@pytest.mark.django_db
def test_login_signup_form_missing_name(mocker, client, settings):  # NOQA: F811, E501
    url = reverse('magiclink:signup')
    data = {
        'form_name': 'SignupForm',
        'email': 'test@example.com',
    }
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['This field is required.']
    assert response.context_data['SignupForm'].errors['name'] == error
