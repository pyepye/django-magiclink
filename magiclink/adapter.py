from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django import forms
from django.http import HttpRequest
from django.utils.module_loading import import_string

from . import settings, utils

if TYPE_CHECKING:
    from .models import MagicLink


class MagicLinkAdapter:
    def get_client_ip(self, request: HttpRequest) -> str | None:
        return utils.get_client_ip(request)

    def check_request(
        self, request: HttpRequest, email: str, form: forms.Form
    ) -> str | None:
        """
        Return the reason to reject a request for a magic link, or None
        """
        for path in settings.SPAM_CHECKS:
            reason = import_string(path)(request, email, form)
            if reason:
                return reason
        return None

    async def acheck_request(
        self, request: HttpRequest, email: str, form: forms.Form
    ) -> str | None:
        return await sync_to_async(self.check_request)(request, email, form)

    def send_email(self, magiclink: "MagicLink", request: HttpRequest) -> None:
        magiclink.deliver_email(
            magiclink.generate_url(request),
            magiclink.generate_unsubscribe_url(request),
        )

    async def asend_email(self, magiclink: "MagicLink", request: HttpRequest) -> None:
        await sync_to_async(self.send_email)(magiclink, request)


def get_adapter() -> MagicLinkAdapter:
    return import_string(settings.ADAPTER)()
