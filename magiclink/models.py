from urllib.parse import urlencode, urljoin

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.core.mail import send_mail
from django.db import models
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import settings
from .adapter import get_adapter
from .signals import magiclink_sent
from .utils import anonymize_ip

User = get_user_model()


UNSUBSCRIBE_SALT = "magiclink.unsubscribe"


class MagicLinkError(Exception):
    pass


def sign_unsubscribe_email(email: str) -> str:
    return signing.dumps(email, salt=UNSUBSCRIBE_SALT)


def unsign_unsubscribe_email(value: str) -> str:
    """
    Return the email address in a signed value, or raise signing.BadSignature
    """
    return signing.loads(value, salt=UNSUBSCRIBE_SALT)


class MagicLink(models.Model):
    email = models.EmailField()
    token = models.TextField()
    expiry = models.DateTimeField()
    redirect_url = models.TextField()
    disabled = models.BooleanField(default=False)
    times_used = models.IntegerField(default=0)
    cookie_value = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.expiry}"

    def used(self) -> bool:
        """
        Count one use of the link. Return False and count nothing if another
        request used or disabled the link after this instance was loaded.
        """
        times_used = self.times_used + 1
        disabled = times_used >= settings.TOKEN_USES
        claimed = self._unchanged().update(times_used=times_used, disabled=disabled)
        if claimed:
            self.times_used, self.disabled = times_used, disabled
        return bool(claimed)

    async def aused(self) -> bool:
        times_used = self.times_used + 1
        disabled = times_used >= settings.TOKEN_USES
        claimed = await self._unchanged().aupdate(
            times_used=times_used, disabled=disabled
        )
        if claimed:
            self.times_used, self.disabled = times_used, disabled
        return bool(claimed)

    def _unchanged(self) -> "models.QuerySet[MagicLink]":
        return MagicLink.objects.filter(
            pk=self.pk, disabled=False, times_used=self.times_used
        )

    def disable(self) -> None:
        self.times_used += 1
        self.disabled = True
        self.save()

    async def adisable(self) -> None:
        self.times_used += 1
        self.disabled = True
        await self.asave()

    def generate_url(self, request: HttpRequest) -> str:
        url_path = reverse(settings.LOGIN_VERIFY_URL)

        params = {"token": self.token}
        if settings.VERIFY_INCLUDE_EMAIL:
            params["email"] = self.email
        query = urlencode(params)

        return self._absolute_url(request, f"{url_path}?{query}")

    def generate_unsubscribe_url(self, request: HttpRequest) -> str:
        """
        Return an empty string if login emails do not include an unsubscribe link.
        All login emails go to users, so with IGNORE_UNSUBSCRIBE_IF_USER the link
        would have no effect.
        """
        if not settings.UNSUBSCRIBE_LINK or settings.IGNORE_UNSUBSCRIBE_IF_USER:
            return ""
        query = urlencode({"email": sign_unsubscribe_email(self.email)})
        url_path = f"{reverse('magiclink:unsubscribe')}?{query}"
        return self._absolute_url(request, url_path)

    def _absolute_url(self, request: HttpRequest, url_path: str) -> str:
        if settings.SITE_URL:
            return urljoin(settings.SITE_URL, url_path)

        domain = get_current_site(request).domain
        scheme = request.is_secure() and "https" or "http"
        return urljoin(f"{scheme}://{domain}", url_path)

    def send(self, request: HttpRequest) -> None:
        if not settings.IGNORE_UNSUBSCRIBE_IF_USER:
            unsubscribed = MagicLinkUnsubscribe.objects.filter(email=self.email)
            if unsubscribed.exists():
                raise MagicLinkError("Email address is on the unsubscribe list")

        get_adapter().send_email(self, request)
        magiclink_sent.send(sender=self.__class__, magiclink=self, request=request)

    async def asend(self, request: HttpRequest) -> None:
        if not settings.IGNORE_UNSUBSCRIBE_IF_USER:
            unsubscribed = MagicLinkUnsubscribe.objects.filter(email=self.email)
            if await unsubscribed.aexists():
                raise MagicLinkError("Email address is on the unsubscribe list")

        await get_adapter().asend_email(self, request)
        await magiclink_sent.asend(
            sender=self.__class__, magiclink=self, request=request
        )

    def deliver_email(self, url: str, unsubscribe_url: str = "") -> None:
        user = User.objects.get(email=self.email)
        context = {
            "subject": settings.EMAIL_SUBJECT,
            "user": user,
            "magiclink": url,
            "unsubscribe_url": unsubscribe_url,
            "expiry": self.expiry,
            "ip_address": self.ip_address,
            "created": self.created,
            "require_same_ip": settings.REQUIRE_SAME_IP,
            "require_same_browser": settings.REQUIRE_SAME_BROWSER,
            "token_uses": settings.TOKEN_USES,
            "style": settings.EMAIL_STYLES,
        }
        plain = render_to_string(settings.EMAIL_TEMPLATE_NAME_TEXT, context)
        html = render_to_string(settings.EMAIL_TEMPLATE_NAME_HTML, context)
        send_mail(
            subject=settings.EMAIL_SUBJECT,
            message=plain,
            recipient_list=[user.email],
            from_email=djsettings.DEFAULT_FROM_EMAIL,
            html_message=html,
        )

    def validate(
        self,
        request: HttpRequest,
        email: str = "",
    ) -> AbstractUser:
        error, should_disable = self._link_error(request, email)
        if error:
            if should_disable:
                self.disable()
            raise MagicLinkError(error)

        user = User.objects.get(email=self.email)
        error = self._user_error(user)
        if error:
            self.disable()
            raise MagicLinkError(error)

        return user

    async def avalidate(
        self,
        request: HttpRequest,
        email: str = "",
    ) -> AbstractUser:
        error, should_disable = self._link_error(request, email)
        if error:
            if should_disable:
                await self.adisable()
            raise MagicLinkError(error)

        user = await User.objects.aget(email=self.email)
        error = self._user_error(user)
        if error:
            await self.adisable()
            raise MagicLinkError(error)

        return user

    def _link_error(self, request: HttpRequest, email: str) -> tuple[str, bool]:
        """
        Return why the link can not be used (or an empty string) and if the link
        should be disabled because of it
        """
        if settings.EMAIL_IGNORE_CASE and email:
            email = email.lower()

        if settings.VERIFY_INCLUDE_EMAIL and self.email != email:
            return "Email address does not match", False

        if timezone.now() > self.expiry:
            return "Magic link has expired", True

        if settings.REQUIRE_SAME_IP:
            client_ip = get_adapter().get_client_ip(request)
            if client_ip and settings.ANONYMIZE_IP:
                client_ip = anonymize_ip(client_ip)
            if self.ip_address != client_ip:
                return (
                    "IP address is different from the IP "
                    "address used to request the magic link"
                ), True

        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f"magiclink{self.pk}"
            if self.cookie_value != request.COOKIES.get(cookie_name):
                return (
                    "Browser is different from the browser "
                    "used to request the magic link"
                ), True

        if self.times_used >= settings.TOKEN_USES:
            return "Magic link has been used too many times", True

        return "", False

    def _user_error(self, user: AbstractUser) -> str:
        if not settings.IGNORE_IS_ACTIVE_FLAG and not getattr(user, "is_active", True):
            return "This user has been deactivated"

        if not settings.ALLOW_SUPERUSER_LOGIN and user.is_superuser:
            return "You can not login to a super user account using a magic link"

        if not settings.ALLOW_STAFF_LOGIN and user.is_staff:
            return "You can not login to a staff account using a magic link"

        return ""


class MagicLinkUnsubscribe(models.Model):
    email = models.EmailField()

    def __str__(self):
        return self.email
