import os

SECRET_KEY = 'magiclink-test'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

ROOT_URLCONF = 'tests.urls'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'tests',
    'magiclink',
]

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

AUTHENTICATION_BACKENDS = (
    'magiclink.backends.MagicLinkBackend',
    'django.contrib.auth.backends.ModelBackend',
)

MAGICLINK_TOKEN_LENGTH = 50
MAGICLINK_AUTH_TIMEOUT = 300
MAGICLINK_TOKEN_USES = 1
MAGICLINK_REQUIRE_SIGNUP = True
MAGICLINK_EMAIL_IGNORE_CASE = True
MAGICLINK_ALLOW_SUPERUSER_LOGIN = True
MAGICLINK_ALLOW_STAFF_LOGIN = True
MAGICLINK_INCLUDE_USER = True
MAGICLINK_REQUIRE_BROWSER = True
MAGICLINK_REQUIRE_SAME_IP = True
# MAGICLINK_WELCOME_EMAIL_TEMPLATE_NAME = 'welcome.html'
MAGICLINK_EMAIL_STYLES = {
    'logo_url': '',
    'background_color': '#ffffff',
    'main_text_color': '#000000',
    'button_background_color': '#0078be',
    'button_text_color': '#ffffff',
}
MAGICLINK_LOGIN_SENT_REDIRECT = '/auth/login/sent/'
