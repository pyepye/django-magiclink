from importlib import reload
from time import time

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.urls import reverse

from magiclink.models import MagicLink

from .fixtures import magic_link, user  # NOQA: F401

User = get_user_model()


@pytest.mark.django_db
def test_login_end_to_end(mocker, settings, client, user):  # NOQA: F811
    spy = mocker.spy(MagicLink, 'generate_url')

    login_url = reverse('magiclink:login')
    data = {'email': user.email}
    client.post(login_url, data, follow=True)
    verify_url = spy.spy_return
    response = client.get(verify_url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('needs_login')

    url = reverse('magiclink:logout')
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('no_login')

    url = reverse('needs_login')
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == reverse('magiclink:login')


def test_login_page_get(client):
    url = reverse('magiclink:login')
    response = client.get(url)
    assert response.context_data['login_form']
    assert response.status_code == 200


def test_signup_require_signup_context(client):
    from magiclink import settings as mlsettings

    url = reverse('magiclink:login')
    response = client.get(url)
    assert response.context_data['require_signup'] == mlsettings.REQUIRE_SIGNUP
    response = client.post(url)
    assert response.context_data['require_signup'] == mlsettings.REQUIRE_SIGNUP


@pytest.mark.django_db
def test_login_post(mocker, client, user, settings):  # NOQA: F811
    from magiclink import settings as mlsettings
    send_mail = mocker.patch('magiclink.models.send_mail')

    url = reverse('magiclink:login')
    data = {'email': user.email}
    response = client.post(url, data, enforce_csrf_checks=True)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    usr = User.objects.get(email=user.email)
    assert usr
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink
    if mlsettings.REQUIRE_SAME_BROWSER:
        cookie_name = f'magiclink{magiclink.pk}'
        assert response.cookies[cookie_name].value == magiclink.cookie_value

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
    assert response.url == reverse('magiclink:login_sent')


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
    assert response.url == reverse('magiclink:login_sent')
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
def test_login_too_many_tokens(client, user, magic_link):  # NOQA: F811
    request = HttpRequest()
    ml = magic_link(request)

    url = reverse('magiclink:login')
    data = {'email': ml.email}
    response = client.post(url, data)
    assert response.status_code == 200
    error = ['Too many magic login requests']
    assert response.context_data['login_form'].errors['email'] == error


@pytest.mark.django_db
def test_login_antispam(settings, client, user, freezer):  # NOQA: F811
    freezer.move_to('2000-01-01T00:00:00')

    submit_time = 1
    settings.MAGICLINK_ANTISPAM_FORMS = True
    settings.MAGICLINK_ANTISPAM_FIELD_TIME = submit_time
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email, 'load_time': time() - submit_time}

    response = client.post(url, data)
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')


@pytest.mark.django_db
def test_login_not_active(settings, client, user):  # NOQA: F811
    user.is_active = False
    user.save()

    url = reverse('magiclink:login')
    data = {'email': user.email}

    response = client.post(url, data)
    assert response.status_code == 200
    error = ['This user has been deactivated']
    assert response.context_data['login_form'].errors['email'] == error


@pytest.mark.django_db
def test_login_not_active_ignore_flag(settings, client, user):  # NOQA: F811
    settings.MAGICLINK_IGNORE_IS_ACTIVE_FLAG = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    user.is_active = False
    user.save()

    url = reverse('magiclink:login')
    data = {'email': user.email}

    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink


@pytest.mark.django_db
def test_login_antispam_submit_too_fast(settings, client, user, freezer):  # NOQA: F811,E501
    freezer.move_to('2000-01-01T00:00:00')

    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email, 'load_time': time()}

    response = client.post(url, data)
    assert response.status_code == 200
    form_errors = response.context['login_form'].errors
    assert form_errors['load_time'] == ['Form filled out too fast - bot detected']  # NOQA: E501


@pytest.mark.django_db
def test_login_antispam_missing_load_time(settings, client, user):  # NOQA: F811,E501
    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email}

    response = client.post(url, data)
    assert response.status_code == 200
    form_errors = response.context['login_form'].errors
    assert form_errors['load_time'] == ['This field is required.']


@pytest.mark.django_db
def test_login_antispam_invalid_load_time(settings, client, user):  # NOQA: F811,E501
    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email, 'load_time': 'test'}

    response = client.post(url, data)
    assert response.status_code == 200
    form_errors = response.context['login_form'].errors
    assert form_errors['load_time'] == ['Invalid value']


@pytest.mark.django_db
def test_login_antispam_url_value(settings, client, user):  # NOQA: F811
    settings.MAGICLINK_ANTISPAM_FORMS = True
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    data = {'email': user.email, 'url': 'test'}

    response = client.post(url, data)
    assert response.status_code == 200
    form_errors = response.context['login_form'].errors
    assert form_errors['url'] == ['url should be empty']


@pytest.mark.django_db
def test_login_post_redirect_url(mocker, client, user, settings):  # NOQA: F811
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    redirect_url = reverse('no_login')
    url = f'{url}?next={redirect_url}'
    data = {'email': user.email}
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    usr = User.objects.get(email=user.email)
    assert usr
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink.redirect_url == redirect_url


@pytest.mark.django_db
def test_login_post_redirect_url_unsafe(mocker, client, user, settings):  # NOQA: F811,E501
    from magiclink import settings as mlsettings
    reload(mlsettings)

    url = reverse('magiclink:login')
    url = f'{url}?next=https://test.com/'
    data = {'email': user.email}
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse('magiclink:login_sent')
    usr = User.objects.get(email=user.email)
    assert usr
    magiclink = MagicLink.objects.get(email=user.email)
    assert magiclink.redirect_url == reverse('needs_login')
