import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .fixtures import user  # NOQA: F401

User = get_user_model()


@pytest.mark.django_db
def test_logout(client, user, settings):  # NOQA: F811
    client.force_login(user)
    url = reverse('magiclink:logout')
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse('no_login')

    needs_login_url = reverse('needs_login')
    needs_login_response = client.get(needs_login_url)
    assert needs_login_response.status_code == 302
    assert response.url == reverse(settings.LOGOUT_REDIRECT_URL)


@pytest.mark.django_db
def test_logout_with_next(client, user, settings):  # NOQA: F811
    client.force_login(user)
    url = reverse('magiclink:logout')
    empty_url = reverse('no_login')
    url = f'{url}?next={empty_url}'
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == empty_url

    needs_login_url = reverse('needs_login')
    needs_login_response = client.get(needs_login_url)
    assert needs_login_response.status_code == 302
    assert response.url == reverse(settings.LOGOUT_REDIRECT_URL)
