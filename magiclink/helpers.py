from datetime import timedelta
from uuid import uuid4

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.db.utils import IntegrityError

from . import settings
from .models import MagicLink
from .utils import get_client_ip

User = get_user_model()


def create_magiclink(email, request, redirect_url=''):
    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    if not redirect_url:
        redirect_url = djsettings.LOGIN_REDIRECT_URL

    expiry = timezone.now() + timedelta(seconds=settings.AUTH_TIMEOUT)
    magic_link = MagicLink.objects.create(
        email=email,
        token=get_random_string(length=settings.AUTH_TIMEOUT),
        expiry=expiry,
        redirect_url=redirect_url,
        cookie_value=str(uuid4()),
        ip_address=get_client_ip(request),
    )
    return magic_link


def create_user(email, username='', first_name='', last_name=''):
    user_fields = [field.name for field in User._meta.get_fields()]

    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    if not username and settings.EMAIL_AS_USERNAME:
        username = email

    if username and 'username' in user_fields:
        user = User.objects.create(
            email=email,
            username=username,
        )
    elif 'username' in user_fields:
        # Set a random username if we need to set a username and
        # EMAIL_AS_USERNAME is False
        user = None
        while not user:
            try:
                user = User.objects.create(
                    email=email, username=get_random_string(length=10),
                )
            except IntegrityError:
                pass
    else:
        user = User.objects.create(email=email)

    if 'first_name' in user_fields:
        user.first_name = first_name
    if 'last_name' in user_fields:
        user.last_name = last_name
    if 'full_name' in user_fields:
        user.full_name = f'{first_name} {last_name}'
    if 'name' in user_fields:
        user.name = f'{first_name} {last_name}'
    user.save()

    return user
