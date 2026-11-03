from importlib import reload
from time import time

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.http.cookie import SimpleCookie
from django.urls import reverse

from magiclink import settings as mlsettings
from magiclink.adapter import MagicLinkAdapter, get_adapter
from magiclink.forms import sign_load_time
from magiclink.helpers import acreate_magiclink, create_magiclink
from magiclink.models import MagicLink, MagicLinkError, MagicLinkUnsubscribe
from magiclink.signals import magiclink_sent, spam_detected

User = get_user_model()
ADAPTER_PATH = "tests.test_adapter"


class IpAdapter(MagicLinkAdapter):
    def get_client_ip(self, request):
        return "203.0.113.7"


class RejectAdapter(MagicLinkAdapter):
    calls = []

    def check_request(self, request, email, form):
        self.calls.append(email)
        return "Rejected by the adapter"


class RecordingAdapter(MagicLinkAdapter):
    sent = []

    def send_email(self, magiclink, request):
        self.sent.append((magiclink.pk, magiclink.generate_url(request)))


class AsyncAdapter(MagicLinkAdapter):
    sent = []

    async def asend_email(self, magiclink, request):
        self.sent.append(magiclink.pk)


@pytest.fixture
def use_adapter(settings):
    def _use(name):
        settings.MAGICLINK_ADAPTER = f"{ADAPTER_PATH}.{name}"
        reload(mlsettings)

    return _use


@pytest.fixture
def spam_receiver(mocker):
    handler = mocker.Mock()
    spam_detected.connect(handler, weak=False)
    yield handler
    spam_detected.disconnect(handler)


def test_get_adapter_default():
    assert type(get_adapter()) is MagicLinkAdapter


def test_get_adapter_custom(use_adapter):
    use_adapter("IpAdapter")
    assert type(get_adapter()) is IpAdapter


def test_adapter_bad_value(settings):
    settings.MAGICLINK_ADAPTER = 1
    with pytest.raises(ImproperlyConfigured):
        reload(mlsettings)


def test_default_get_client_ip():
    request = HttpRequest()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    assert MagicLinkAdapter().get_client_ip(request) == "10.0.0.1"


def test_default_check_request_allows():
    assert (
        MagicLinkAdapter().check_request(HttpRequest(), "a@example.com", None) is None
    )


@pytest.mark.asyncio
async def test_default_acheck_request_calls_sync_method(use_adapter):
    use_adapter("RejectAdapter")
    reason = await get_adapter().acheck_request(HttpRequest(), "a@example.com", None)
    assert reason == "Rejected by the adapter"


@pytest.mark.django_db
def test_client_ip_from_adapter_used_for_the_full_login(client, use_adapter, user):
    use_adapter("IpAdapter")
    client.post(reverse("magiclink:login"), {"email": user.email})
    ml = MagicLink.objects.get(email=user.email)
    assert ml.ip_address == "203.0.113.0"

    # The test client connects from 127.0.0.1, so this login only passes if the
    # verify step also gets the IP address from the adapter
    url = f"{reverse('magiclink:login_verify')}?token={ml.token}&email={ml.email}"
    response = client.get(url)
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_check_request_rejects_login(client, use_adapter, user, spam_receiver):
    RejectAdapter.calls.clear()
    use_adapter("RejectAdapter")
    response = client.post(reverse("magiclink:login"), {"email": user.email})

    assert response.status_code == 200
    assert response.context["login_form"].errors["email"] == ["Rejected by the adapter"]
    assert RejectAdapter.calls == [user.email]
    assert not MagicLink.objects.exists()
    assert mail.outbox == []
    assert spam_receiver.call_args.kwargs["reason"] == "Rejected by the adapter"


@pytest.mark.django_db
def test_check_request_quiet_reject(client, settings, use_adapter, user):
    settings.MAGICLINK_ANTISPAM_QUIET_REJECT = True
    use_adapter("RejectAdapter")
    response = client.post(reverse("magiclink:login"), {"email": user.email})

    assert response.status_code == 302
    assert response.url == reverse("magiclink:login_sent")
    assert not MagicLink.objects.exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_check_request_not_called_for_invalid_form(client, use_adapter):
    RejectAdapter.calls.clear()
    use_adapter("RejectAdapter")
    client.post(reverse("magiclink:login"), {"email": "not-an-email"})
    assert RejectAdapter.calls == []


@pytest.mark.django_db
def test_check_request_login_does_not_create_user(client, settings, use_adapter):
    settings.MAGICLINK_REQUIRE_SIGNUP = False
    use_adapter("RejectAdapter")
    client.post(reverse("magiclink:login"), {"email": "new@example.com"})
    assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
def test_check_request_rejects_signup(client, use_adapter, spam_receiver):
    use_adapter("RejectAdapter")
    data = {"form_name": "SignupFormEmailOnly", "email": "new@example.com"}
    response = client.post(reverse("magiclink:signup"), data)

    assert response.status_code == 200
    assert response.context["SignupFormEmailOnly"].errors["email"] == [
        "Rejected by the adapter"
    ]
    assert not User.objects.filter(email="new@example.com").exists()
    assert mail.outbox == []
    spam_receiver.assert_called_once()


@pytest.mark.django_db
def test_form_spam_sends_reason(client, settings, user, spam_receiver):
    settings.MAGICLINK_ANTISPAM_FORMS = True
    reload(mlsettings)
    data = {"email": user.email, "load_time": sign_load_time(time()), "url": "bot"}
    client.post(reverse("magiclink:login"), data)
    assert spam_receiver.call_args.kwargs["reason"]


@pytest.mark.django_db
def test_send_email_override_replaces_delivery(client, use_adapter, user, mocker):
    RecordingAdapter.sent.clear()
    use_adapter("RecordingAdapter")
    handler = mocker.Mock()
    magiclink_sent.connect(handler, weak=False)
    try:
        response = client.post(reverse("magiclink:login"), {"email": user.email})
    finally:
        magiclink_sent.disconnect(handler)

    ml = MagicLink.objects.get(email=user.email)
    assert response.status_code == 302
    assert mail.outbox == []
    assert RecordingAdapter.sent[0][0] == ml.pk
    assert ml.token in RecordingAdapter.sent[0][1]
    handler.assert_called_once()

    ml.deliver_email(RecordingAdapter.sent[0][1])
    assert ml.token in mail.outbox[0].body


@pytest.mark.django_db
def test_login_with_link_from_custom_adapter(client, use_adapter, user):
    RecordingAdapter.sent.clear()
    use_adapter("RecordingAdapter")
    client.post(reverse("magiclink:login"), {"email": user.email})

    ml = MagicLink.objects.get(email=user.email)
    client.cookies = SimpleCookie(
        {**client.cookies, f"magiclink{ml.pk}": ml.cookie_value}
    )
    response = client.get(RecordingAdapter.sent[0][1])
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_send_unsubscribed_does_not_reach_adapter(rf, use_adapter, user):
    RecordingAdapter.sent.clear()
    use_adapter("RecordingAdapter")
    request = rf.get("/")
    ml = create_magiclink(user.email, request)
    MagicLinkUnsubscribe.objects.create(email=user.email)
    with pytest.raises(MagicLinkError):
        ml.send(request)
    assert RecordingAdapter.sent == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_asend_uses_asend_email(rf, use_adapter, user):
    AsyncAdapter.sent.clear()
    use_adapter("AsyncAdapter")
    request = rf.get("/")
    ml = await acreate_magiclink(user.email, request)
    await ml.asend(request)
    assert AsyncAdapter.sent == [ml.pk]
    assert mail.outbox == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_default_asend_email_sends_the_email(rf, user):
    request = rf.get("/")
    ml = await acreate_magiclink(user.email, request)
    await ml.asend(request)
    assert ml.token in mail.outbox[0].body


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_asend_unsubscribed(rf, user):
    request = rf.get("/")
    ml = await acreate_magiclink(user.email, request)
    await MagicLinkUnsubscribe.objects.acreate(email=user.email)
    with pytest.raises(MagicLinkError):
        await ml.asend(request)
    assert mail.outbox == []
    assert await sync_to_async(MagicLink.objects.count)() == 1
