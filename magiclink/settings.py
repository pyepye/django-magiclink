import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

try:
    TOKEN_LENGTH = int(getattr(settings, 'MAGICLINK_TOKEN_LENGTH', 50))
except ValueError:
    raise ImproperlyConfigured('"MAGICLINK_TOKEN_LENGTH" must be an integer')
else:
    if TOKEN_LENGTH < 20:
        warning = ('Shorter MAGICLINK_TOKEN_LENGTH values make your login more'
                   'sussptable to brute force attacks')
        warnings.warn(warning, RuntimeWarning)

EMAIL_VERIFY = getattr(settings, 'MAGICLINK_EMAIL_VERIFY', True)
if not isinstance(EMAIL_VERIFY, bool):
    raise ImproperlyConfigured('"MAGICLINK_EMAIL_VERIFY" must be a boolean')

try:
    # In seconds
    AUTH_TIMEOUT = int(getattr(settings, 'MAGICLINK_AUTH_TIMEOUT', 300))
except ValueError:
    raise ImproperlyConfigured('"MAGICLINK_AUTH_TIMEOUT" must be an integer')

try:
    TOKEN_USES = int(getattr(settings, 'MAGICLINK_TOKEN_USES', 1))
except ValueError:
    raise ImproperlyConfigured('"MAGICLINK_TOKEN_USES" must be an integer')

EMAIL_IGNORE_CASE = getattr(settings, 'MAGICLINK_EMAIL_IGNORE_CASE', True)
if not isinstance(EMAIL_IGNORE_CASE, bool):
    raise ImproperlyConfigured('"MAGICLINK_EMAIL_IGNORE_CASE" must be a boolean')  # NOQA: E501

REQUIRE_SIGNUP = getattr(settings, 'MAGICLINK_REQUIRE_SIGNUP', True)
if not isinstance(REQUIRE_SIGNUP, bool):
    raise ImproperlyConfigured('"MAGICLINK_REQUIRE_SIGNUP" must be a boolean')
SIGNUP_LOGIN_REDIRECT = getattr(settings, 'MAGICLINK_SIGNUP_LOGIN_REDIRECT', '')   # NOQA: E501

EMAIL_AS_USERNAME = getattr(settings, 'MAGICLINK_EMAIL_AS_USERNAME', True)
if not isinstance(EMAIL_AS_USERNAME, bool):
    raise ImproperlyConfigured('"MAGICLINK_EMAIL_AS_USERNAME" must be a boolean')  # NOQA: E501

ALLOW_SUPERUSER_LOGIN = getattr(settings, 'MAGICLINK_ALLOW_SUPERUSER_LOGIN', True)  # NOQA: E501
if not isinstance(ALLOW_SUPERUSER_LOGIN, bool):
    raise ImproperlyConfigured('"MAGICLINK_ALLOW_SUPERUSER_LOGIN" must be a boolean')  # NOQA: E501

ALLOW_STAFF_LOGIN = getattr(settings, 'MAGICLINK_ALLOW_STAFF_LOGIN', True)
if not isinstance(ALLOW_STAFF_LOGIN, bool):
    raise ImproperlyConfigured('"MAGICLINK_ALLOW_STAFF_LOGIN" must be a boolean')  # NOQA: E501

VERIFY_WITH_EMAIL = getattr(settings, 'MAGICLINK_VERIFY_WITH_EMAIL', True)
if not isinstance(VERIFY_WITH_EMAIL, bool):
    raise ImproperlyConfigured('"MAGICLINK_VERIFY_WITH_EMAIL" must be a boolean')  # NOQA: E501

REQUIRE_BROWSER = getattr(settings, 'MAGICLINK_REQUIRE_BROWSER', True)
if not isinstance(REQUIRE_BROWSER, bool):
    raise ImproperlyConfigured('"MAGICLINK_REQUIRE_BROWSER" must be a boolean')

REQUIRE_SAME_IP = getattr(settings, 'MAGICLINK_REQUIRE_SAME_IP', True)
if not isinstance(REQUIRE_SAME_IP, bool):
    raise ImproperlyConfigured('"MAGICLINK_REQUIRE_SAME_IP" must be a boolean')

SIGNUP_EMAIL_TEMPLATE = getattr(settings, 'MAGICLINK_SIGNUP_EMAIL_TEMPLATE', '')  # NOQA: E501
if SIGNUP_EMAIL_TEMPLATE:
    try:
        get_template(SIGNUP_EMAIL_TEMPLATE)
    except TemplateDoesNotExist:
        error = f'Can\'t find a template which matches MAGICLINK_SIGNUP_EMAIL_TEMPLATE template "{SIGNUP_EMAIL_TEMPLATE}"'  # NOQA: E501
        raise ImproperlyConfigured(error)


EMAIL_STYLES = {
    'logo_url': '',
    'background_color': '#ffffff',
    'main_text_color': '#000000',
    'button_background_color': '#0078be',
    'button_text_color': '#ffffff',
}
EMAIL_STYLES = getattr(settings, 'MAGICLINK_EMAIL_STYLES', EMAIL_STYLES)
if EMAIL_STYLES and not isinstance(EMAIL_STYLES, dict):
    raise ImproperlyConfigured('"MAGICLINK_EMAIL_STYLES" must be a dict')

LOGIN_SENT_REDIRECT = getattr(settings, 'MAGICLINK_LOGIN_SENT_REDIRECT', 'magiclink:login_sent')   # NOQA: E501

EMAIL_SUBJECT = getattr(settings, 'MAGICLINK_EMAIL_SUBJECT', 'Your login magic link')   # NOQA: E501
