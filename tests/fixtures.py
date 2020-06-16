import pytest
from django.contrib.auth import get_user_model

from magiclink.helpers import create_magiclink

User = get_user_model()


@pytest.fixture()
def user():
    user = User.objects.create(email='test@example.com')
    return user


@pytest.fixture
def magic_link(user):

    def _create(request):
        return create_magiclink(user.email, request, redirect_url='')

    return _create
