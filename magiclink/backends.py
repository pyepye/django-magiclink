from django.contrib.auth import get_user_model
from django.utils import timezone

from . import settings
from .models import MagicLink
from .utils import get_client_ip

User = get_user_model()


class MagicLinkBackend:

    def authenticate(self, request, token=None, email=None):
        if settings.EMAIL_VERIFY and not email:
            return

        if settings.EMAIL_IGNORE_CASE:
            email = email.lower()

        magiclink = MagicLink.objects.filter(token=token, disabled=False)
        if email:
            magiclink = magiclink.filter(email=email)
        if not magiclink:
            return

        magiclink = magiclink.first()

        # ToDo: Check expiry
        if magiclink.expiry_time > timezone.now():
            magiclink.disable()
            return

        if settings.REQUIRE_SAME_IP:
            if magiclink.ip_address != get_client_ip(request):
                magiclink.disable()
                return

        if settings.REQUIRE_BROWSER:
            if magiclink.cookie != request.COOKIES.get('magiclink'):
                magiclink.disable()
                return

        if magiclink.times_used >= settings.TOKEN_USES:
            magiclink.disable()
            return

        if not settings.REQUIRE_SIGNUP:
            user = self.get_or_create_user(self, email)
        else:
            user = User.objects.get(email=magiclink.email)

        if not settings.ALLOW_SUPERUSER_LOGIN and user.is_superuser:
            magiclink.disable()
            return

        if not settings.ALLOW_STAFF_LOGIN and user.is_staff:
            magiclink.disable()
            return

        magiclink.used()

        return user

    def get_or_create_user(self, email):
        fields = [field.name for field in User._meta.get_fields()]
        if 'username' in fields:
            # The model contains a username, so we should try to fill it in.
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'username': 'u' + generate_token()[:8]}
            )
        else:
            user, created = User.objects.get_or_create(email=email)
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return
