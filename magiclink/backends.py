import logging

from django.contrib.auth import get_user_model
from django.utils import timezone

from . import settings
from .models import MagicLink
from .utils import get_client_ip

User = get_user_model()
log = logging.getLogger(__name__)


class MagicLinkBackend():

    def authenticate(self, request, token=None, email=None):
        log.debug(f'MagicLink authenticate token: {token} - email: {email}')

        if not token:
            log.warning('Token missing from authentication')
            return

        if settings.VERIFY_INCLUDE_EMAIL and not email:
            log.warning('Email address not supplied with token')
            return

        if settings.EMAIL_IGNORE_CASE and email:
            log.debug('Setting email to lowercase')
            email = email.lower()

        try:
            magiclink = MagicLink.objects.get(token=token, disabled=False)
        except MagicLink.DoesNotExist:
            log.warning('Valid MagicLink with token could not be found')
            return

        if settings.VERIFY_INCLUDE_EMAIL and magiclink.email != email:
            log.warning(f'Email address "{email}" does not match for {magiclink.pk}')  # NOQA: E501
            return

        magiclink = MagicLink.objects.get(token=token)

        if timezone.now() > magiclink.expiry:
            log.warning(f'MagicLink {magiclink.pk} is expired')
            magiclink.disable()
            return

        if settings.REQUIRE_SAME_IP:
            if magiclink.ip_address != get_client_ip(request):
                log.warning(f'MagicLink {magiclink.pk} ip_address did not match request')  # NOQA: E501
                magiclink.disable()
                return

        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f'magiclink{magiclink.pk}'
            if magiclink.cookie_value != request.COOKIES.get(cookie_name):
                log.warning(f'MagicLink {magiclink.pk} cookie did not match request')  # NOQA: E501
                magiclink.disable()
                return

        if magiclink.times_used >= settings.TOKEN_USES:
            log.warning(f'MagicLink {magiclink.pk} used too many times')
            magiclink.disable()
            return

        user = User.objects.get(email=magiclink.email)

        if not settings.ALLOW_SUPERUSER_LOGIN and user.is_superuser:
            log.warning(f'Superuser login is disabled')
            magiclink.disable()
            return

        if not settings.ALLOW_STAFF_LOGIN and user.is_staff:
            log.warning(f'Staff login is disabled')
            magiclink.disable()
            return

        magiclink.used()
        log.info(f'{user} can be authenticated via MagicLink {magiclink.pk}')
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return
