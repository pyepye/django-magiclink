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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tests',
    'magiclink',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    'magiclink.backends.MagicLinkBackend',
    'django.contrib.auth.backends.ModelBackend',
]

MAGICLINK_TOKEN_LENGTH = 50
MAGICLINK_AUTH_TIMEOUT = 300
MAGICLINK_TOKEN_USES = 1
MAGICLINK_REQUIRE_SIGNUP = True
MAGICLINK_EMAIL_IGNORE_CASE = True
MAGICLINK_ALLOW_SUPERUSER_LOGIN = False
MAGICLINK_ALLOW_STAFF_LOGIN = False
MAGICLINK_INCLUDE_USER = True
MAGICLINK_REQUIRE_BROWSER = True
MAGICLINK_REQUIRE_SAME_IP = True
MAGICLINK_EMAIL_STYLES = {
    'logo_url': '',
    'background_color': '#ffffff',
    'main_text_color': '#000000',
    'button_background_color': '#0078be',
    'button_text_color': '#ffffff',
}
MAGICLINK_LOGIN_SENT_REDIRECT = '/auth/login/sent/'
