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
    redirect_url: str = "",
) -> MagicLink:
    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    limit = timezone.now() - timedelta(seconds=settings.LOGIN_REQUEST_TIME_LIMIT)
    over_limit = MagicLink.objects.filter(email=email, created__gte=limit)
    if over_limit.exists():
        raise MagicLinkError("Too many magic login requests")

    if settings.ONE_TOKEN_PER_USER:
        magic_links = MagicLink.objects.filter(email=email, disabled=False)
        magic_links.update(disabled=True)

    return MagicLink.objects.create(**_magiclink_fields(email, request, redirect_url))


async def acreate_magiclink(
    email: str,
    request: HttpRequest,
    redirect_url: str = "",
) -> MagicLink:
    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    limit = timezone.now() - timedelta(seconds=settings.LOGIN_REQUEST_TIME_LIMIT)
    over_limit = MagicLink.objects.filter(email=email, created__gte=limit)
    if await over_limit.aexists():
        raise MagicLinkError("Too many magic login requests")

    if settings.ONE_TOKEN_PER_USER:
        magic_links = MagicLink.objects.filter(email=email, disabled=False)
        await magic_links.aupdate(disabled=True)

    return await MagicLink.objects.acreate(
        **_magiclink_fields(email, request, redirect_url)
    )


def _magiclink_fields(
    email: str, request: HttpRequest, redirect_url: str
) -> dict[str, object]:
    if not redirect_url:
        redirect_url = get_url_path(djsettings.LOGIN_REDIRECT_URL)

    client_ip = None
    if settings.REQUIRE_SAME_IP:
        client_ip = get_client_ip(request)
        if client_ip and settings.ANONYMIZE_IP:
            client_ip = client_ip[: client_ip.rfind(".") + 1] + "0"

    return {
        "email": email,
        "token": get_random_string(length=settings.TOKEN_LENGTH),
        "expiry": timezone.now() + timedelta(seconds=settings.AUTH_TIMEOUT),
        "redirect_url": redirect_url,
        "cookie_value": str(uuid4()),
        "ip_address": client_ip,
    }


def get_or_create_user(
    email: str, username: str = "", first_name: str = "", last_name: str = ""
):
    User = get_user_model()

    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        pass

    user_details, needs_random_username = _new_user_details(
        email, username, first_name, last_name
    )
    if not needs_random_username:
        return User.objects.create(**user_details)

    while True:
        user_details["username"] = get_random_string(length=10)
        try:
            return User.objects.create(**user_details)
        except IntegrityError:  # pragma: no cover
            pass


async def aget_or_create_user(
    email: str, username: str = "", first_name: str = "", last_name: str = ""
):
    User = get_user_model()

    if settings.EMAIL_IGNORE_CASE:
        email = email.lower()

    try:
        return await User.objects.aget(email=email)
    except User.DoesNotExist:
        pass

    user_details, needs_random_username = _new_user_details(
        email, username, first_name, last_name
    )
    if not needs_random_username:
        return await User.objects.acreate(**user_details)

    while True:
        user_details["username"] = get_random_string(length=10)
        try:
            return await User.objects.acreate(**user_details)
        except IntegrityError:  # pragma: no cover
            pass


def _new_user_details(
    email: str, username: str, first_name: str, last_name: str
) -> tuple[dict[str, str], bool]:
    """
    Return the fields for a new user and if a random username must be added
    """
    user_fields = [field.name for field in get_user_model()._meta.get_fields()]

    if not username and settings.EMAIL_AS_USERNAME:
        username = email

    user_details = {"email": email}
    if "first_name" in user_fields and first_name:
        user_details["first_name"] = first_name
    if "last_name" in user_fields and last_name:
        user_details["last_name"] = last_name
    if "full_name" in user_fields:
        user_details["full_name"] = f"{first_name} {last_name}".strip()
    if "name" in user_fields:
        user_details["name"] = f"{first_name} {last_name}".strip()

    if "username" not in user_fields:
        return user_details, False

    if not username:
        # Set a random username if we need to set a username and
        # EMAIL_AS_USERNAME is False
        return user_details, True

    user_details["username"] = username
    return user_details, False
