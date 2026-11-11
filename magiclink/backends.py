import logging

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from . import settings
from .models import MagicLink, MagicLinkError
from .signals import login_failed, login_succeeded

User = get_user_model()
log = logging.getLogger(__name__)

ALREADY_USED = "Magic link has already been used"


class MagicLinkBackend:
    def authenticate(
        self,
        request: HttpRequest,
        token: str = "",
        email: str = "",
    ):
        if not self._credentials_given(token, email):
            return

        try:
            magiclink = MagicLink.objects.get(token=token)
        except MagicLink.DoesNotExist:
            log.warning(f"MagicLink not found for {email}")
            login_failed.send(
                sender=self.__class__,
                request=request,
                magiclink=None,
                reason="A magic link with that token could not be found",
            )
            return

        if magiclink.disabled:
            log.warning(f'MagicLink "{magiclink.pk}" is disabled')
            login_failed.send(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason="Magic link is disabled",
            )
            return

        try:
            user = magiclink.validate(request, email)
        except MagicLinkError as error:
            log.warning(error)
            login_failed.send(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason=str(error),
            )
            return

        if not magiclink.used():
            log.warning(f'MagicLink "{magiclink.pk}" was used by another request')
            login_failed.send(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason=ALREADY_USED,
            )
            return

        log.info(f"{user} authenticated via MagicLink")
        login_succeeded.send(
            sender=self.__class__, request=request, user=user, magiclink=magiclink
        )
        return user

    async def aauthenticate(
        self,
        request: HttpRequest,
        token: str = "",
        email: str = "",
    ):
        if not self._credentials_given(token, email):
            return

        try:
            magiclink = await MagicLink.objects.aget(token=token)
        except MagicLink.DoesNotExist:
            log.warning(f"MagicLink not found for {email}")
            await login_failed.asend(
                sender=self.__class__,
                request=request,
                magiclink=None,
                reason="A magic link with that token could not be found",
            )
            return

        if magiclink.disabled:
            log.warning(f'MagicLink "{magiclink.pk}" is disabled')
            await login_failed.asend(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason="Magic link is disabled",
            )
            return

        try:
            user = await magiclink.avalidate(request, email)
        except MagicLinkError as error:
            log.warning(error)
            await login_failed.asend(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason=str(error),
            )
            return

        if not await magiclink.aused():
            log.warning(f'MagicLink "{magiclink.pk}" was used by another request')
            await login_failed.asend(
                sender=self.__class__,
                request=request,
                magiclink=magiclink,
                reason=ALREADY_USED,
            )
            return

        log.info(f"{user} authenticated via MagicLink")
        await login_succeeded.asend(
            sender=self.__class__, request=request, user=user, magiclink=magiclink
        )
        return user

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return
        return user if self.user_can_authenticate(user) else None

    async def aget_user(self, user_id):
        try:
            user = await User.objects.aget(pk=user_id)
        except User.DoesNotExist:
            return
        return user if self.user_can_authenticate(user) else None

    def user_can_authenticate(self, user) -> bool:
        if settings.IGNORE_IS_ACTIVE_FLAG:
            return True
        return getattr(user, "is_active", True)

    def _credentials_given(self, token: str, email: str) -> bool:
        log.debug(f"MagicLink authenticate for {email}")

        if not token:
            log.warning("Token missing from authentication")
            return False

        if settings.VERIFY_INCLUDE_EMAIL and not email:
            log.warning("Email address not supplied with token")
            return False

        return True
