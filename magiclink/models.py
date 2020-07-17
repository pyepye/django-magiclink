from urllib.parse import urlencode, urljoin

from django.conf import settings as djsettings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse

from . import settings

# from django.db.models.signals import post_save

User = get_user_model()


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

    def used(self):
        self.times_used += 1
        if self.times_used >= settings.TOKEN_USES:
            self.disabled = True
        self.save()

    def disable(self):
        self.times_used += 1
        self.disabled = True
        self.save()

    def get_magic_link_url(self, request):
        url_path = reverse("magiclink:login_verify")

        params = {'token': self.token}
        if settings.VERIFY_WITH_EMAIL:
            params['email'] = self.email
        query = urlencode(params)

        url_path = f'{url_path}?{query}'
        domain = get_current_site(request).domain
        scheme = request.is_secure() and "https" or "http"
        url = urljoin(f'{scheme}://{domain}', url_path)
        return url

    def send(self, request):
        user = User.objects.get(email=self.email)
        context = {
            'subject': settings.EMAIL_SUBJECT,
            'user': user,
            'magiclink': self.get_magic_link_url(request),
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
