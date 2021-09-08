from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from magiclink.models import MagicLink


@pytest.mark.django_db
def test_magiclink_clear_logins():
    # Valid Magic Links
    for index in range(2):
        MagicLink.objects.create(
            email='test@example.com',
            token='fake',
            expiry=timezone.now(),
            redirect_url='',
        )

    # Magic Links which expired 2 weeks ago so should be removed
    two_weeks_ago = timezone.now() - timedelta(days=14)
    for index in range(2):
        MagicLink.objects.create(
            email='test@example.com',
            token='fake',
            expiry=two_weeks_ago,
            redirect_url='',
        )

    # Disabled Magic Links which should be removed
    for index in range(2):
        magic_link = MagicLink.objects.create(
            email='test@example.com',
            token='fake',
            expiry=timezone.now(),
            redirect_url='',
        )
        magic_link.disable()

    call_command('magiclink_clear_logins')

    all_magiclinks = MagicLink.objects.all()
    assert all_magiclinks.count() == 2
    for link in all_magiclinks:
        assert not link.disabled
        assert link.expiry > timezone.now() - timedelta(days=6)
