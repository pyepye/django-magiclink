from importlib import reload

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.http.cookie import SimpleCookie
from django.urls import reverse

from magiclink import ratelimit
from magiclink import settings as mlsettings
from magiclink.models import MagicLink
from magiclink.settings import RateLimitRule, parse_rate_limit_rules
from magiclink.signals import login_failed, spam_detected
from magiclink.views import TOO_MANY_REQUESTS

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def limits(settings):
    def _set(**rules):
        settings.MAGICLINK_RATE_LIMITS = rules

    return _set


def make_request(ip="10.0.0.1"):
    request = HttpRequest()
    request.META["REMOTE_ADDR"] = ip
    return request


def make_user(email):
    return User.objects.create(username=email, email=email)


@pytest.mark.parametrize(
    ("rules", "expected"),
    [
        ("", []),
        ("100/m", [RateLimitRule(100, 60, None)]),
        ("5/h/ip", [RateLimitRule(5, 3600, "ip")]),
        (
            "5/h/ip, 3/10m/email",
            [RateLimitRule(5, 3600, "ip"), RateLimitRule(3, 600, "email")],
        ),
        ("1/30s", [RateLimitRule(1, 30, None)]),
        ("1/2d", [RateLimitRule(1, 172800, None)]),
    ],
)
def test_parse_rules(rules, expected):
    assert parse_rate_limit_rules(rules) == expected


@pytest.mark.parametrize(
    "rules", ["5", "5/x", "a/m", "5/m/user", "5/0m", "5/h/ip/extra", "5/h ip"]
)
def test_parse_bad_rules(rules):
    with pytest.raises(ImproperlyConfigured):
        parse_rate_limit_rules(rules)


@pytest.mark.parametrize(
    "value", ["5/m", {"other": "5/m"}, {"request": 5}, {"request": "bad"}]
)
def test_rate_limits_bad_value(settings, value):
    settings.MAGICLINK_RATE_LIMITS = value
    with pytest.raises(ImproperlyConfigured):
        reload(mlsettings)


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("Name@Example.com", "name@example.com"),
        ("name+tag@example.com", "name@example.com"),
        ("name+a+b@example.com", "name@example.com"),
        (" name@example.com ", "name@example.com"),
    ],
)
def test_normalise_email(email, expected):
    assert ratelimit.normalise_email(email) == expected


def test_no_rules_never_limits():
    assert not ratelimit.hit("request", make_request(), "a@example.com")
    assert not ratelimit.is_limited("request", make_request(), "a@example.com")


def test_hit_limit_per_ip(limits):
    limits(request="2/m/ip")
    assert not ratelimit.hit("request", make_request())
    assert not ratelimit.hit("request", make_request())
    assert ratelimit.hit("request", make_request())
    assert not ratelimit.hit("request", make_request("10.0.1.1"))


def test_each_ipv4_address_counts_on_its_own(limits):
    limits(request="1/m/ip")
    assert not ratelimit.hit("request", make_request("10.0.0.1"))
    assert not ratelimit.hit("request", make_request("10.0.0.200"))
    assert ratelimit.hit("request", make_request("10.0.0.1"))


def test_ipv4_mapped_address_counts_as_ipv4(limits):
    limits(request="1/m/ip")
    assert not ratelimit.hit("request", make_request("10.0.0.1"))
    assert ratelimit.hit("request", make_request("::ffff:10.0.0.1"))


def test_ipv6_grouped_by_64(limits):
    limits(request="1/m/ip")
    assert not ratelimit.hit("request", make_request("2001:db8:0:1::1"))
    assert ratelimit.hit("request", make_request("2001:db8:0:1:ffff::2"))
    assert not ratelimit.hit("request", make_request("2001:db8:0:2::1"))


def test_no_ip_skips_ip_rule(limits):
    limits(request="1/m/ip")
    request = HttpRequest()
    assert not ratelimit.hit("request", request)
    assert not ratelimit.hit("request", request)


def test_limit_per_email_ignores_case_and_tags(limits):
    limits(request="2/m/email")
    request = make_request()
    assert not ratelimit.hit("request", request, "name@example.com")
    assert not ratelimit.hit("request", request, "NAME+1@example.com")
    assert ratelimit.hit("request", request, "name+2@example.com")
    assert not ratelimit.hit("request", request, "other@example.com")


def test_no_email_skips_email_rule(limits):
    limits(request="1/m/email")
    assert not ratelimit.hit("request", make_request())
    assert not ratelimit.hit("request", make_request())


def test_site_limit_is_shared_by_all_ips(limits):
    limits(request_site="1/m")
    assert not ratelimit.hit("request_site", make_request("10.0.0.1"))
    assert ratelimit.hit("request_site", make_request("192.0.2.1"))


def test_any_rule_over_limit_limits(limits):
    limits(request="10/m/ip,1/m/email")
    assert not ratelimit.hit("request", make_request(), "a@example.com")
    assert ratelimit.hit("request", make_request(), "a@example.com")


def test_rule_names_are_separate(limits):
    limits(request="1/m/ip", verify_failed="1/m/ip")
    assert not ratelimit.hit("request", make_request())
    assert not ratelimit.hit("verify_failed", make_request())


def test_window_resets(limits, time_machine):
    time_machine.move_to("2030-01-01T00:00:00", tick=False)
    limits(request="1/m/ip")
    assert not ratelimit.hit("request", make_request())
    assert ratelimit.hit("request", make_request())
    time_machine.move_to("2030-01-01T00:01:00", tick=False)
    assert not ratelimit.hit("request", make_request())


def test_hit_key_evicted_before_incr(limits, mocker):
    limits(request="1/m/ip")
    mocker.patch.object(cache, "incr", side_effect=ValueError)
    assert not ratelimit.hit("request", make_request())


def test_is_limited_does_not_count(limits):
    limits(verify_failed="1/m/ip")
    assert not ratelimit.is_limited("verify_failed", make_request())
    assert not ratelimit.is_limited("verify_failed", make_request())
    ratelimit.hit("verify_failed", make_request())
    assert ratelimit.is_limited("verify_failed", make_request())


def test_cache_keys_do_not_contain_the_email(limits, mocker):
    limits(request="1/m/email")
    add = mocker.spy(cache, "add")
    ratelimit.hit("request", make_request(), "secret@example.com")
    assert "secret" not in add.call_args.args[0]


@pytest.mark.asyncio
async def test_ahit_and_ais_limited(limits):
    limits(request="1/m/ip,5/m/email", verify_failed="1/m/ip")
    assert not await ratelimit.ahit("request", make_request(), "a@example.com")
    assert await ratelimit.ahit("request", make_request(), "a@example.com")

    assert not await ratelimit.ais_limited("verify_failed", make_request())
    await ratelimit.ahit("verify_failed", make_request())
    assert await ratelimit.ais_limited("verify_failed", make_request())


@pytest.mark.asyncio
async def test_ahit_key_evicted_before_incr(limits, mocker):
    limits(request="1/m/ip")
    mocker.patch.object(cache, "aincr", side_effect=ValueError)
    assert not await ratelimit.ahit("request", make_request())


@pytest.fixture
def spam_receiver(mocker):
    handler = mocker.Mock()
    spam_detected.connect(handler, weak=False)
    yield handler
    spam_detected.disconnect(handler)


@pytest.mark.django_db
def test_login_request_limit_per_ip(client, limits, spam_receiver):
    limits(request="1/h/ip")
    url = reverse("magiclink:login")
    first = make_user("one@example.com")
    second = make_user("two@example.com")

    assert client.post(url, {"email": first.email}).status_code == 302
    response = client.post(url, {"email": second.email})

    assert response.status_code == 200
    assert response.context["login_form"].errors == {"email": [TOO_MANY_REQUESTS]}
    assert len(mail.outbox) == 1
    assert not MagicLink.objects.filter(email=second.email).exists()
    assert spam_receiver.call_args.kwargs["reason"] == TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_login_limit_counts_invalid_forms_and_hides_their_errors(client, limits):
    limits(request="1/h/ip")
    url = reverse("magiclink:login")
    first = client.post(url, {"email": "nobody@example.com"})
    assert "could not find a user" in str(first.context["login_form"].errors)

    second = client.post(url, {"email": "nobody2@example.com"})
    assert second.context["login_form"].errors == {"email": [TOO_MANY_REQUESTS]}


@pytest.mark.django_db
def test_login_limit_ignores_spoofed_forwarded_header(client, limits, user):
    limits(request="1/h/ip")
    url = reverse("magiclink:login")
    client.post(url, {"email": user.email}, headers={"x-forwarded-for": "1.1.1.1"})
    response = client.post(
        url, {"email": user.email}, headers={"x-forwarded-for": "2.2.2.2"}
    )
    assert response.context["login_form"].errors == {"email": [TOO_MANY_REQUESTS]}


@pytest.mark.django_db
def test_login_limit_per_email_stops_plus_tags(client, limits):
    limits(request="1/h/email")
    url = reverse("magiclink:login")
    client.post(url, {"email": "bot+1@example.com"})
    response = client.post(url, {"email": "bot+2@example.com"})
    assert response.context["login_form"].errors == {"email": [TOO_MANY_REQUESTS]}


@pytest.mark.django_db
def test_login_limit_quiet_reject(client, settings, limits, user):
    settings.MAGICLINK_ANTISPAM_QUIET_REJECT = True
    limits(request="0/h/ip")
    response = client.post(reverse("magiclink:login"), {"email": user.email})
    assert response.status_code == 302
    assert response.url == reverse("magiclink:login_sent")
    assert mail.outbox == []


@pytest.mark.django_db
def test_site_limit_only_counts_requests_that_can_send(client, limits):
    limits(request_site="1/h")
    url = reverse("magiclink:login")
    first = make_user("one@example.com")
    second = make_user("two@example.com")

    client.post(url, {"email": "nobody@example.com"})
    assert client.post(url, {"email": first.email}).status_code == 302
    response = client.post(url, {"email": second.email})

    assert response.context["login_form"].errors == {"email": [TOO_MANY_REQUESTS]}
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_request_limit(client, limits):
    limits(request="1/h/ip")
    url = reverse("magiclink:signup")
    data = {"form_name": "SignupFormEmailOnly", "email": "new1@example.com"}
    assert client.post(url, data).status_code == 302

    data["email"] = "new2@example.com"
    response = client.post(url, data)
    assert response.status_code == 200
    assert response.context["SignupFormEmailOnly"].errors == {
        "email": [TOO_MANY_REQUESTS]
    }
    assert not User.objects.filter(email="new2@example.com").exists()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_site_limit_creates_no_user(client, limits):
    limits(request_site="0/h")
    data = {"form_name": "SignupFormEmailOnly", "email": "new@example.com"}
    response = client.post(reverse("magiclink:signup"), data)
    assert response.context["SignupFormEmailOnly"].errors == {
        "email": [TOO_MANY_REQUESTS]
    }
    assert not User.objects.filter(email="new@example.com").exists()


def verify_url(ml, token=None):
    return (
        f"{reverse('magiclink:login_verify')}"
        f"?token={token or ml.token}&email={ml.email}"
    )


@pytest.mark.django_db
def test_verify_failed_limit_blocks_a_good_link_until_the_window_ends(
    client, limits, user, mocker, time_machine
):
    time_machine.move_to("2030-01-01T00:00:00", tick=False)
    limits(verify_failed="2/m/ip")
    handler = mocker.Mock()
    login_failed.connect(handler, weak=False)
    client.post(reverse("magiclink:login"), {"email": user.email})
    ml = MagicLink.objects.get(email=user.email)
    client.cookies = SimpleCookie({f"magiclink{ml.pk}": ml.cookie_value})

    try:
        client.get(verify_url(ml, token="wrong1"))
        client.get(verify_url(ml, token="wrong2"))
        response = client.get(verify_url(ml))
    finally:
        login_failed.disconnect(handler)

    assert response.status_code == 200
    assert response.context["login_error"] == TOO_MANY_REQUESTS
    assert "_auth_user_id" not in client.session
    assert handler.call_args.kwargs["reason"] == TOO_MANY_REQUESTS
    assert handler.call_args.kwargs["magiclink"] is None

    ml.refresh_from_db()
    assert not ml.disabled
    assert ml.times_used == 0

    time_machine.move_to("2030-01-01T00:01:00", tick=False)
    response = client.get(verify_url(ml))
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_verify_success_does_not_count(client, limits, user):
    limits(verify_failed="1/m/ip")
    client.post(reverse("magiclink:login"), {"email": user.email})
    ml = MagicLink.objects.get(email=user.email)
    client.cookies = SimpleCookie({f"magiclink{ml.pk}": ml.cookie_value})
    assert client.get(verify_url(ml)).status_code == 302
    assert not ratelimit.is_limited("verify_failed", make_request("127.0.0.1"))


@pytest.mark.django_db
def test_verify_limited_with_failed_redirect(client, settings, limits):
    settings.MAGICLINK_LOGIN_FAILED_REDIRECT = "/failed/"
    limits(verify_failed="0/m/ip")
    response = client.get(reverse("magiclink:login_verify"), {"token": "a"})
    assert response.status_code == 302
    assert response.url == "/failed/"
