import logging

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from . import settings
from .models import MagicLink, MagicLinkError

User = get_user_model()
log = logging.getLogger(__name__)


class MagicLinkBackend():

    def authenticate(
        self,
        request: HttpRequest,
        token: str = '',
        email: str = '',
    ):
        log.debug(f'MagicLink authenticate token: {token} - email: {email}')

        if not token:
            log.warning('Token missing from authentication')
            return

        if settings.VERIFY_INCLUDE_EMAIL and not email:
            log.warning('Email address not supplied with token')
            return

        try:
            magiclink = MagicLink.objects.get(token=token)
        except MagicLink.DoesNotExist:
            log.warning(f'MagicLink with token "{token}" not found')
            return

        if magiclink.disabled:
            log.warning(f'MagicLink "{magiclink.pk}" is disabled')
            return

        try:
            user = magiclink.validate(request, email)
        except MagicLinkError as error:
            log.warning(error)
            return

        magiclink.used()
        log.info(f'{user} authenticated via MagicLink')
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return
