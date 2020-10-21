from urllib.parse import urlencode, urljoin

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.db import models
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import settings
from .utils import get_client_ip

User = get_user_model()


class MagicLinkError(Exception):
    pass


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
        return f'{self.email} - {self.expiry}'

    def used(self) -> None:
        self.times_used += 1
        if self.times_used >= settings.TOKEN_USES:
            self.disabled = True
        self.save()

    def disable(self) -> None:
        self.times_used += 1
        self.disabled = True
        self.save()

    def generate_url(self, request: HttpRequest) -> str:
        url_path = reverse("magiclink:login_verify")

        params = {'token': self.token}
        if settings.VERIFY_INCLUDE_EMAIL:
            params['email'] = self.email
        query = urlencode(params)

        url_path = f'{url_path}?{query}'
        domain = get_current_site(request).domain
        scheme = request.is_secure() and "https" or "http"
        url = urljoin(f'{scheme}://{domain}', url_path)
        return url

    def send(self, request: HttpRequest) -> None:
        user = User.objects.get(email=self.email)
        context = {
            'subject': settings.EMAIL_SUBJECT,
            'user': user,
            'magiclink': self.generate_url(request),
            'expiry': self.expiry,
            'ip_address': self.ip_address,
            'created': self.created,
            'require_same_ip': settings.REQUIRE_SAME_IP,
            'require_same_browser': settings.REQUIRE_SAME_BROWSER,
            'token_uses': settings.TOKEN_USES,
            'style': settings.EMAIL_STYLES,
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
        email: str = '',
    ) -> AbstractUser:
        if settings.EMAIL_IGNORE_CASE and email:
            email = email.lower()

        if settings.VERIFY_INCLUDE_EMAIL and self.email != email:
            raise MagicLinkError('Email address does not match')

        if timezone.now() > self.expiry:
            self.disable()
            raise MagicLinkError('Magic link has expired')

        if settings.REQUIRE_SAME_IP:
            if self.ip_address != get_client_ip(request):
                self.disable()
                raise MagicLinkError('IP address is different from the IP '
                                     'address used to request the magic link')

        if settings.REQUIRE_SAME_BROWSER:
            cookie_name = f'magiclink{self.pk}'
            if self.cookie_value != request.COOKIES.get(cookie_name):
                self.disable()
                raise MagicLinkError('Browser is different from the browser '
                                     'used to request the magic link')

        if self.times_used >= settings.TOKEN_USES:
            self.disable()
            raise MagicLinkError('Magic link has been used too many times')

        user = User.objects.get(email=self.email)

        if not settings.ALLOW_SUPERUSER_LOGIN and user.is_superuser:
            self.disable()
            raise MagicLinkError(
                'You can not login to a super user account using a magic link')

        if not settings.ALLOW_STAFF_LOGIN and user.is_staff:
            self.disable()
            raise MagicLinkError(
                'You can not login to a staff account using a magic link')

        return user
