# Django MagicLink


Passwordless Authentication for Django with Magic Links.

This package was created with a focus on [ease of setup](#steps-to-impliment), [security](#security) and testing (coverage is currently at 100%). The idea is to use sane defaults to quickly create secure single-use token authentication for Django.

![](example.gif)


## Install

```bash
pip install django-magiclink
```


## Setup

The setup of the app is simple but has a few steps and a few templates that need overriding.

1. [Install the app](#install)
1. [Configure the app](#configuration) adding urls and settings. There are also a number of [additional configuration settings](#configuration-settings)
1. [Set up the login page](#login-page) by overriding the login page template
1. [Override the login sent page HTML](#login-sent-page)
1. [Customise the login failed page](#login-failed-page)
1. [Set up the magic link email](#magic-link-email) (optional) by setting the email logo and colours. It's also possible to override the email templates
1. [Create a signup page](#signup-page) (optional) depending on your settings configuration


### Basic login flow

1. The user signs up via the sign up page (This can be skipped if `MAGICLINK_REQUIRE_SIGNUP = False`)
1. They enter their email on the login page to request a magic link
1. A magic link is sent to users email address
1. The user is redirected to a login sent page
1. The user clicks on the magic link in their email
1. The user is logged in and redirected


*If you want to create a different passwordless login flow see the [Manual usage](#manual-usage) section*


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
*Note: MagicLinkBackend should be placed at the top of AUTHENTICATION_BACKENDS* to ensure it is used as the primary login backend.


Add the following settings to your `settings.py` (you will need to replace the template names in the below steps):
```python
# Set Djangos login URL to the magiclink login page
LOGIN_URL = 'magiclink:login'

MAGICLINK_LOGIN_TEMPLATE_NAME = 'magiclink/login.html'
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = 'magiclink/login_sent.html'
MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = 'magiclink/login_failed.html'

# Optional:
# If this setting is set to False a user account will be created the first
# time a user requests a login link.
MAGICLINK_REQUIRE_SIGNUP = True
MAGICLINK_SIGNUP_TEMPLATE_NAME = 'magiclink/signup.html'
```

See [additional configuration settings](#configuration-settings) for all of the different available settings.


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

```html
<h1>Check your email</h1>
<p>We have sent you a magic link to your email address</p>
<p>Please click the link to be logged in automatically</p>
```


#### Login failed page

If the user tries to use an invalid magic token they will be shown a custom error page. To override the HTML for this page you can set the `MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME` setting. If you would like to return a 404 page you can set this setting to a empty string (or any falsy value).

The reasons for the login failing is passed through as the context variable `{{ login_error }}`

To help tailor the error page and explain the possible reasons the user could not login the following context variables are provided:

* `{{ login_error }}` - The reason the login failed (raised by `MagicLink.validate()`)
* `{{ one_token_per_user }}` - The value of the `MAGICLINK_ONE_TOKEN_PER_USER` setting
* `{{ require_same_browser }}` - The value of the `MAGICLINK_REQUIRE_SAME_BROWSER` setting
* `{{ require_same_ip }}` - The value of the `MAGICLINK_REQUIRE_SAME_IP` setting
* `{{ allow_superuser_login }}` - The value of the `MAGICLINK_ALLOW_SUPERUSER_LOGIN` setting
* `{{ allow_staff_login }}` - The value of the `MAGICLINK_ALLOW_STAFF_LOGIN` setting


For an example of this page see the [default login failed template](https://github.com/pyepye/django-magiclink/blob/master/magiclink/templates/magiclink/login_failed.html)


#### Magic link email

The login email which includes the magic link needs to be configured. By default, a simple HTML template is used which can be adapted to your own branding using the `MAGICLINK_EMAIL_STYLES` setting, or you can override the template (see below)

This `MAGICLINK_EMAIL_STYLES` setting should be a dict with the following key values:

```python
MAGICLINK_EMAIL_STYLES = {
    'logo_url': 'https://example.com/logo.png',
    'background-colour': '#ffffff',
    'main-text-color': '#000000',
    'button-background-color': '#0078be',
    'button-text-color': '#ffffff',
}
```
*Note: The logo URL must be a full URL. For email client support you should use either a jpeg or png.*

If this email template is not to your liking you can override the email templates (one for text and one for html). To do so you need to override the `MAGICLINK_EMAIL_TEMPLATE_NAME_TEXT` and `MAGICLINK_EMAIL_TEMPLATE_NAME_HTML` settings.  If you override these templates the following context variables are available:

* `{{ subject }}` - The subject of the email "Your login magic link"
* `{{ magiclink }}` - The magic link URL
* `{{ user }}` - The full user object
* `{{ expiry }}` - Datetime for when the magiclink expires
* `{{ ip_address }}` - The IP address of the person who requested the magic link
* `{{ created }}` - Datetime of when the magic link was created
* `{{ require_same_ip }}` - The value of `MAGICLINK_REQUIRE_SAME_IP`
* `{{ require_same_browser }}` - The value of `MAGICLINK_REQUIRE_SAME_BROWSER`
* `{{ token_uses }}` - The value of `MAGICLINK_TOKEN_USES`


#### Signup page

If you want users to have to signup before being able to log in you will want to override the signup page template using the `MAGICLINK_SIGNUP_TEMPLATE_NAME` setting. This is needed when `MAGICLINK_REQUIRE_SIGNUP = True`. On successful signup the user will be sent a login email with a magic link.

When overriding this template please ensure the following content is included:

```html
<form action="{% url 'magiclink:signup' %}" method="post">
    {% csrf_token %}
    {{ SignupForm }}
    <button type='submit'>Signup</button>
</form>
<p>Already have an account? <a href='{% url 'magiclink:login' %}'>Log in here</a></p>
```

There are several forms made avalible in the context on this page depending on what information you want to collect:
* **SignupFormEmailOnly** - Only includes an `email` field
* **SignupForm** - Includes `name` and `email` fields
* **SignupFormWithUsername** - Includes `username` and `email` fields
* **SignupFormFull** - Includes `username`, `name` and `email` fields


Like the login for the sign up flow can be overridden if you require more information from the user on signup. See the login/setup docs for more details.


#### Configuration settings

Below are the different settings that can be overridden. To do so place the setting into your `settings.py`.

*Note: Each of the url / redirect settings can either be a URL or url name*

```python

# Override the login page template. See 'Login page' in the Setup section
MAGICLINK_LOGIN_TEMPLATE_NAME = 'myapp/login.html'

# Override the login page template. See 'Login sent page' in the Setup section
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = 'myapp/login_sent.html'

# Override the template that shows when the user tries to login with a
# magic link that is not valid. See 'Login failed page' in the Setup section
MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = 'magiclink/login_failed.html'


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
MAGICLINK_SIGNUP_LOGIN_REDIRECT = '/welcome/'

# Change the url a user is redirect to after requesting a magic link
MAGICLINK_LOGIN_SENT_REDIRECT = 'magiclink:login_sent'

# Ensure the branding of the login email is correct. This setting is not needed
# if you override the `login_email.html` template
MAGICLINK_EMAIL_STYLES = {
    'logo_url': '',
    'background-colour': '#ffffff',
    'main-text-color': '#000000',
    'button-background-color': '#0078be',
    'button-text-color': '#ffffff',
}

# If you want to use your own email templates you can override the text and
# html templates used with:
MAGICLINK_EMAIL_TEMPLATE_NAME_TEXT = 'myapp/login_email.text'
MAGICLINK_EMAIL_TEMPLATE_NAME_HTML = 'myapp/login_email.html'

# How long a magic link is valid for before returning an error
MAGICLINK_AUTH_TIMEOUT = 300  # In second - Default is 5 minutes

# Email address is not case sensitive. If this setting is set to True all
# emails addresses will be set to lowercase before any checks are run against it
MAGICLINK_IGNORE_EMAIL_CASE = True

# When creating a user assign their email as the username (if the User model
# has a username field)
MAGICLINK_EMAIL_AS_USERNAME = True

# Allow superusers to login via a magic link
MAGICLINK_ALLOW_SUPERUSER_LOGIN = True

# Allow staff users to login via a magic link
MAGICLINK_ALLOW_STAFF_LOGIN = True

# Ignore the Django user model's is_active flag for login requests
MAGICLINK_IGNORE_IS_ACTIVE_FLAG = True

# Override the default magic link length
# Warning: Overriding this setting has security implications, shorter tokens
# are much more susceptible to brute force attacks*
MAGICLINK_TOKEN_LENGTH = 50

# Require the user email to be included in the verification link
# Warning: If this is set to false tokens are more vulnerable to brute force
MAGICLINK_VERIFY_INCLUDE_EMAIL = True

# Ensure the user who clicked magic link used the same browser as the
# initial login request.
# Note: This can cause issues on devices where the default browser is
# different from the browser being used by the user such as on iOS)
MAGICLINK_REQUIRE_SAME_BROWSER = True

# Ensure the user who clicked magic link has the same IP address as the
# initial login request.
MAGICLINK_REQUIRE_SAME_IP = True

# The number of times a login token can be used before being disabled
MAGICLINK_TOKEN_USES = 1

# How often a user can request a new login token (basic rate limiting).
MAGICLINK_LOGIN_REQUEST_TIME_LIMIT = 30  # In seconds

# Disable all other tokens for a user when a new token is requested
MAGICLINK_ONE_TOKEN_PER_USER = True

# Include basic anti spam form fields to help stop bots. False by default
# Note: IF you use the default forms you will need to add CSS to your
# page / stylesheet to hide the labels for the anti spam fields.
# See the login.html or signup.html for an example
MAGICLINK_ANTISPAM_FORMS = False
# The shortest time a user can fill out each field and submit a form without
# being considered a bot. The time is per field and defaults to 1 second.
# This means if the form has 3 fields and the user will need to make more than
# 3 seconds to fill out a form.
MAGICLINK_ANTISPAM_FIELD_TIME = 1
```


## Security

Using magic links can be dangerous as poorly implemented login links can be brute-forced and emails can be forwarded by accident. There are several security measures used to mitigate these risks:

* The one-time password issued will be valid for 5 minutes before it expires
* The user's email is specified alongside login tokens to stop URLs being brute-forced
* Each login token will be at least 20 digits
* The initial request and its response must take place from the same IP address
* The initial request and its response must take place in the same browser
* Each one-time link can only be used once
* Only the last one-time link issued will be accepted. Once the latest one is issued, any others are invalidated.

*Note: Each of the above settings can be overridden / changed when configuring django-magiclink*


## Manual usage

django-magiclink uses a model to help create, send and validate magic links. A `create_magiclink` helper function can be used easily create a MagicLink using the correct settings:

```python
from magiclink.helpers import create_magiclink

# Returns newly created from magiclink.models.MagicLink instance
magiclink = create_magiclink(email, request, redirect_url='')

# Generates the magic link url and sends it in an email
magiclink.send(request)

# If you want to build the magic link from the model instance but don't want to
#  send the email you can you can use:
magic_link_url = magiclink.generate_url(request)
```
