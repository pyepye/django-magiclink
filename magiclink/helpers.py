from datetime import timedelta
from uuid import uuid4

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import get_random_string

from . import settings
from .models import MagicLink, MagicLinkError
from .utils import get_client_ip, get_url_path


def create_magiclink(
    email: str,
    request: HttpRequest,
    redirect_url: str = '',
) -> MagicLink:
    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    limit = timezone.now() - timedelta(seconds=settings.LOGIN_REQUEST_TIME_LIMIT)  # NOQA: E501
    over_limit = MagicLink.objects.filter(email=email, created__gte=limit)
    if over_limit:
        raise MagicLinkError('Too many magic login requests')

    if settings.ONE_TOKEN_PER_USER:
        magic_links = MagicLink.objects.filter(email=email, disabled=False)
        magic_links.update(disabled=True)

    if not redirect_url:
        redirect_url = get_url_path(djsettings.LOGIN_REDIRECT_URL)

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


def get_or_create_user(
    email: str,
    username: str = '',
    first_name: str = '',
    last_name: str = ''
):
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

    user_details = {'email': email}
    if 'first_name' in user_fields and first_name:
        user_details['first_name'] = first_name
    if 'last_name' in user_fields and last_name:
        user_details['last_name'] = last_name
    if 'full_name' in user_fields:
        user_details['full_name'] = f'{first_name} {last_name}'.strip()
    if 'name' in user_fields:
        user_details['name'] = f'{first_name} {last_name}'.strip()

    if 'username' in user_fields and not username:
        # Set a random username if we need to set a username and
        # EMAIL_AS_USERNAME is False
        created = False
        while not created:
            user_details['username'] = get_random_string(length=10)
            try:
                user = User.objects.create(**user_details)
                created = True
            except IntegrityError:  # pragma: no cover
                pass
    else:
        if 'username' in user_fields:
            user_details['username'] = username
        user = User.objects.create(**user_details)

    return user
