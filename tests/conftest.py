from importlib import reload

import pytest
from django.contrib.auth import get_user_model

from magiclink import settings as mlsettings
from magiclink.helpers import create_magiclink, get_or_create_user

User = get_user_model()


@pytest.fixture(autouse=True)
def reload_magiclink_settings():
    reload(mlsettings)


@pytest.fixture()
def user():
    user = get_or_create_user(email="test@example.com")
    return user


@pytest.fixture
def magic_link(user):

    def _create(request):
        return create_magiclink(user.email, request, redirect_url="")

    return _create
