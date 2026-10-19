from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command(
        "makemigrations", "magiclink", "--check", "--dry-run", stdout=StringIO()
    )
