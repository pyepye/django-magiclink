import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from magiclink.models import MagicLink

User = get_user_model()


@pytest.mark.django_db
def test_signup_end_to_end(mocker, settings, client):
    spy = mocker.spy(MagicLink, 'get_magic_link_url')

    login_url = reverse('magiclink:signup')
    email = 'test@example.com'
    first_name = 'test'
    last_name = 'name'
    data = {
        'form_name': 'SignupForm',
        'email': email,
        'name': f'{first_name} {last_name}',
    }
    client.post(login_url, data, follow=True)
    verify_url = spy.spy_return
    response = client.get(verify_url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('needs_login')
    user = User.objects.get(email=email)
    assert user.first_name == first_name
    assert user.last_name == last_name

    url = reverse('magiclink:logout')
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('no_login')

    url = reverse('needs_login')
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('magiclink:login')


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
    magiclink = MagicLink.objects.get(email=email)
    assert magiclink
    if mlsettings.REQUIRE_SAME_BROWSER:
        assert response.cookies['magiclink'].value == magiclink.cookie_value

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


@pytest.mark.django_db
def test_signup_form_user_exists(mocker, client):
    email = 'test@example.com'
    User.objects.create(email=email)
    url = reverse('magiclink:signup')

    data = {
        'form_name': 'SignupForm',
        'email': email,
        'name': 'testname',
    }
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['Email address is already linked to an account']
    response.context_data['SignupForm'].errors['email'] == error


@pytest.mark.django_db
def test_signup_form_email_only(mocker, client):
    url = reverse('magiclink:signup')
    email = 'test@example.com'
    data = {
        'form_name': 'SignupFormEmailOnly',
        'email': email,
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')


@pytest.mark.django_db
def test_signup_form_with_username(mocker, client):
    url = reverse('magiclink:signup')
    email = 'test@example.com'
    username = 'usrname'
    data = {
        'form_name': 'SignupFormWithUsername',
        'email': email,
        'username': username,
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    usr = User.objects.get(email=email)
    assert usr.username == username


@pytest.mark.django_db
def test_signup_form_with_username_taken(mocker, client):
    username = 'usrname'
    email = 'test@example.com'
    User.objects.create(username=username, email=email)
    url = reverse('magiclink:signup')
    data = {
        'form_name': 'SignupFormWithUsername',
        'email': email,
        'username': username,
    }
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['username is already linked to an account']
    response.context_data['SignupFormWithUsername'].errors['username'] == error


@pytest.mark.django_db
def test_signup_form_with_username_required(mocker, client):
    username = 'usrname'
    email = 'test@example.com'
    User.objects.create(username=username, email=email)
    url = reverse('magiclink:signup')
    data = {
        'form_name': 'SignupFormWithUsername',
        'email': email,
    }
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['This field is required.']
    response.context_data['SignupFormWithUsername'].errors['username'] == error


@pytest.mark.django_db
def test_signup_form_full(mocker, client):
    url = reverse('magiclink:signup')
    email = 'test@example.com'
    username = 'usrname'
    first_name = 'fname'
    last_name = 'lname'
    data = {
        'form_name': 'SignupFormFull',
        'email': email,
        'username': username,
        'name': f'{first_name} {last_name}'
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    usr = User.objects.get(email=email)
    assert usr.username == username
    assert usr.first_name == first_name
    assert usr.last_name == last_name
