from datetime import timedelta
from uuid import uuid4

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.utils import timezone
from django.utils.crypto import get_random_string

from . import settings
from .models import MagicLink
from .utils import get_client_ip


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


def get_or_create_user(email, username='', first_name='', last_name=''):
    User = get_user_model()

    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        pass
    else:
        return user

    user_fields = [field.name for field in User._meta.get_fields()]

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
            except IntegrityError:  # pragma: no cover
                pass
    else:
        user = User.objects.create(email=email)

    if 'first_name' in user_fields and first_name:
        user.first_name = first_name
    if 'last_name' in user_fields and last_name:
        user.last_name = last_name
    if 'full_name' in user_fields:
        user.full_name = f'{first_name} {last_name}'.strip()
    if 'name' in user_fields:
        user.name = f'{first_name} {last_name}'.strip()
    user.save()

    return user
