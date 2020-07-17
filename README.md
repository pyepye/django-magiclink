# Django MagicLink


Passwordless Authentication for Django with Magic Links.

This package was created with a focus on [ease of setup](#steps-to-impliment) and [security](#security). The idea is to use sane defaults to quickly create secure single-use token authentication for Django.


## Install

```bash
pip install django-magiclink
```


## Setup

The setup of the app is simple but has a few steps and a few templates that need overriding.

1. [Install the app](#install)
1. [Configure the app](#configuration) - There are a large number of [additional configuration settings](#configuration-settings)
1. [Set up the login page](#login-page) by overriding the login page HTML (or create a custom login view)
1. [Override the login sent page HTML](#login-sent-page)
1. [Set up the magic link email](#magic-link-email) by setting the email logo and colours. It's also possible to override the email templates
1. [Create a signup page](#signup-page) (optional) depending on your settings configuration


### Basic login flow

1. The user signs up via the sign up page (This can be skipped if `MAGICLINK_REQUIRE_SIGNUP = False`)
1. They enter their email on the login page to request a magic link
1. A magic link is sent to users email address
1. The user is redirected to a login sent page
1. The user clicks on the magic link in their email
1. The user is logged in and redirected


#### Configuration

Add to the `urlpatterns` in `urls.py`:
```python
urlpatterns = [
    ...
    path('auth/', include('magiclink.urls', namespace='magiclink')),
    ...
]
```

Add `magiclink` to your `INSTALLED_APPS`:
```python
INSTALLED_APPS = (
    ...
    'magiclink',
    ...
)
```

```python
AUTHENTICATION_BACKENDS = (
    'magiclink.backends.MagicLinkBackend',
    ...
    'django.contrib.auth.backends.ModelBackend',
)
```
*Note: MagicLinkBackend should be placed at the top of AUTHENTICATION_BACKENDS* to ensure it is used


Add the following settings to your `settings.py`
```python
# Set Djangos login URL to the magiclink login page
LOGIN_URL = 'magiclink:login'

MAGICLINK_LOGIN_TEMPLATE_NAME = 'myapp/login.html'
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = 'myapp/login_sent.html'

# If this setting is set to False a user account will be created the first time
# a user requests a login link.
MAGICLINK_REQUIRE_SIGNUP = True
MAGICLINK_SIGNUP_TEMPLATE_NAME = 'myapp/signup.html'
```

See [additional configuration settings](#configuration-settings) for all of the different available settings. The most important setting for the sign up/login flow is if signup is required before a login link can be requested. If this is set to False a new user will be created the first time a new email address is used to request a login link


#### Login page

Each login page will need different HTML so you need to set the `MAGICLINK_LOGIN_TEMPLATE_NAME` setting to a template of your own. When overriding this template please ensure the following code is included:

```html
<form action="{% url 'magiclink:login' %}{% if request.GET.next %}?next={{ request.GET.next }}{% endif %}" method="post">
    {% csrf_token %}
    {{ login_form }}
    <button type='submit'>Send login email</button>
</form>
```

See the login docs if you want to create your own login view


#### Login sent page

After the user has requested a magic link, they will be redirected to a success page. The HTML for this page can be overridden using the setting `MAGICLINK_LOGIN_SENT_TEMPLATE_NAME`. It is advised you return a simple message telling the user to check their email:
```
<h1>Check your email</h1>
<p>We have sent you a magic link to your email address</p>
<p>Please click the link to be logged in automatically</p>
```

#### Magic link email

The login email which includes the magic link needs to be configured. By default, a simple HTML template is used which can be adapted to your own branding using the `MAGICLINK_EMAIL_STYLES` setting, or you can override the template (see below)

This `MAGICLINK_EMAIL_STYLES` setting should be a dict with the following key values:

```python
MAGICLINK_EMAIL_STYLES = {
    'logo_url': 'https://example.com/logo.png',  # Full URL. This should be either a jpeg or png due to email clients
    'background-colour': '#ffffff',   # Emails background colour
    'main-text-color': '#000000',  # Color of the text in the email, this should be very different from the background
    'button-background-color': '#0078be',  # Color of the text in the email, this should be very different from the background
    'button-text-color': '#ffffff',  # Color of the button text, this should be very different from the button background
}
```

If this email template is not to your liking you can override the email template by creating your own templates (one for text and one for html) with the names `login_email.txt` and `login_email.html`. If you override these templates the following context variables are available:

* `{{ subject }}` - The subject of the email "Your login magic link"
* `{{ magiclink }}` - The magic link URL
* `{{ user }}` - The full user object


#### Signup page

If you want users to have to signup before being able to log in you will want to override the signup page template. This is needed when `MAGICLINK_REQUIRE_SIGNUP = True`. On successful signup the user will be sent a login email, an optional welcome email can be sent as well.

When overriding this template please ensure the following content is included:

```html
<form action="{% url 'magiclink:signup' %}" method="post">
    {% csrf_token %}
    {{ SignupForm }}
    <button type='submit'>Signup</button>
</form>
<p>Already have an account? <a href='{% url 'magiclink:login' %}'>Log in here</a></p>
```

There are actually several forms avalible in the context on this page depending on what information you want to collect.
* **SignupFormEmailOnly** - Only includes an `email` field
* **SignupForm** - Includes `name` and `email` fields
* **SignupFormWithUsername** - Includes `Username` and `email` fields
* **SignupFormFull** - Includes `username`, `name` and `email` fields


Like the login for the sign up flow can be overridden if you require more information from the user on signup. See the login/setup docs for more details
ToDo: Include docs on how to use post_save signal to send Welcome email?


#### Configuration settings

Below are the different settings that can be overridden. To do so place the setting into you `settings.py`

```python

# Override the login page template. See 'Login page' in the Setup section
MAGICLINK_LOGIN_TEMPLATE_NAME = 'myapp/login.html'

# Override the login page template. See 'Login sent page' in the Setup section
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = 'myapp/login_sent.html'

# If this setting is set to False a user account will be created the first time
# a user requests a login link.
MAGICLINK_REQUIRE_SIGNUP = True
# Override the login page template. See 'Login sent page' in the Setup section
MAGICLINK_SIGNUP_TEMPLATE_NAME = 'myapp/signup.html'

# Set Djangos login redirect URL to be used once the user opens the magic link
# This will be used whenever a ?next parameter is not set on login
LOGIN_REDIRECT_URL = '/accounts/profile/'

# If a new user is created via the signup page use this setting to send them to
# a different url than LOGIN_REDIRECT_URL when clicking the magic link
# This will fall back to LOGIN_REDIRECT_URL
MAGICLINK_SIGNUP_LOGIN_REDIRECT = '/welcome'

# Change the url a user is redirect to after requesting a magic link
MAGICLINK_LOGIN_SENT_REDIRECT = 'magiclink:login_sent'

# Only allow users to log in that have signed up first (i.e. don't create a
# new account on login).
MAGICLINK_REQUIRE_SIGNUP = True

# Ensure the branding of the login email is correct. This setting is not needed
# if you override the `login_email.html` template
MAGICLINK_EMAIL_STYLES = {
    'logo_url': '',
    'background-colour': '#ffffff',
    'main-text-color': '#000000',
    'button-background-color': '#0078be',
    'button-text-color': '#ffffff',
}

# How long a magic link is valid for before returning an error
MAGICLINK_AUTH_TIMEOUT = 300  # In second - Default is 5 minutes

# Email address is not case sensitive. If this setting is set to True all
# emails addresses will be set to lowercase before any checks are run against it
MAGICLINK_IGNORE_EMAIL_CASE = True

# Allow superusers to login via a magic link
MAGICLINK_ALLOW_SUPERUSER_LOGIN = True

# Allow staff users to login via a magic link
MAGICLINK_ALLOW_STAFF_LOGIN = True

# Override the default magic link length
# Warning: Overriding this setting has security implications, shorter tokens
# are much more susceptible to brute force attacks*
MAGICLINK_TOKEN_LENGTH = 0

# Require the user email to be included in the verification link
# Warning: If this is set to false tokens are more vulnerable to brute force
MAGICLINK_VERIFY_WITH_EMAIL = True

# Ensure the user who clicked magic link used the same browser as the
# initial login request.
# Note: This can cause issues on devices where the default browser is
# different from the browser being used by the user such as on iOS)*
MAGICLINK_REQUIRE_SAME_BROWSER = True

# Ensure the user who clicked magic link has the same IP address as the
# initial login request.
MAGICLINK_REQUIRE_SAME_IP = True

# The number of times a login token can be used before being disabled
MAGICLINK_TOKEN_USES = 1

# How often in seconds a user can request a new login token
MAGICLINK_TOKEN_TIME_LIMIT = 30
```


## Security

Using magic links can be dangerous as poorly implemented login links can be brute-forced and emails can be forwarded by accident. There are several security measures used to mitigate these risks:

* The one-time password issued will be valid for 5 minutes before it expires
* The user's email is specified alongside login tokens to stop URLs being brute-forced
* Each login token will be at least 20 digits?
* The initial request and its response must take place from the same IP address
* The initial request and its response must take place in the same browser
* Each one-time link can only be used once
* Only the last one-time link issued will be accepted. Once the latest one is issued, any others are invalidated.

*Note: Each of the above settings can be overridden*


## ToDo
* Implement `MAGICLINK_TOKEN_TIME_LIMIT`
* Implement `MAGICLINK_SIGNUP_LOGIN_REDIRECT`
* Test `VERIFY_WITH_EMAIL = False`
* Test emails or context for emails?
* Add type hinting with mypy / django-stubs
* Create docs and setup Read the Docs
* Add Travis for tests
