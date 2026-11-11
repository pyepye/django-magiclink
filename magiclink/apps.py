from django.apps import AppConfig
from django.core.checks import Tags, register


class MagiclinkConfig(AppConfig):
    name = "magiclink"
    default_auto_field = "django.db.models.AutoField"

    def ready(self) -> None:
        from .checks import check_settings

        register(check_settings, Tags.security)
