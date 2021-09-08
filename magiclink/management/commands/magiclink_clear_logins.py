from datetime import timedelta
from django.utils import timezone

from django.core.management.base import BaseCommand

from ...models import MagicLink
from ... import settings

class Command(BaseCommand):
    help = 'Delete disabled Magic Links'

    def handle(self, *args, **options):
        limit = timezone.now() - timedelta(seconds=settings.LOGIN_REQUEST_TIME_LIMIT)  # NOQA: E501
        week_before = limit - timedelta(days=7)

        for magic_links in MagicLink.objects.filter(expiry__lte=week_before):
            magic_links.disable()

        magic_links = MagicLink.objects.filter(disabled=True)
        self.stdout.write(f'Deleting {magic_links.count()} magic links')

        for magic_links in MagicLink.objects.filter(disabled=True):
            magic_links.delete()
