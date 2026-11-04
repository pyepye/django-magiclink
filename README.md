# Django MagicLink


Passwordless Authentication for Django with Magic Links.

This package was created with a focus on [ease of setup](#steps-to-impliment), [security](#security) and testing (coverage is currently at 100%). The idea is to use sane defaults to quickly create secure single-use token authentication for Django.

![](example.gif)


## Install

```bash
pip install django-magiclink
```

### Supported versions

django-magiclink is tested against the following versions of Django and Python:

| Django | Python |
|---|---|
| 5.2 LTS | 3.11, 3.12, 3.13, 3.14 |
| 6.0 | 3.12, 3.13, 3.14 |
| 6.1 | 3.12, 3.13, 3.14 |

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
LOGIN_URL = "magiclink:login"

MAGICLINK_LOGIN_TEMPLATE_NAME = "magiclink/login.html"
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = "magiclink/login_sent.html"
MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"

# Optional:
# If this setting is set to False a user account will be created the first
# time a user requests a login link.
MAGICLINK_REQUIRE_SIGNUP = True
MAGICLINK_SIGNUP_TEMPLATE_NAME = "magiclink/signup.html"
```

See [additional configuration settings](#configuration-settings) for all of the different available settings.


Once the app has been added to `INSTALLED_APPS` you must run the migrations for `magiclink`

```bash
python manage.py migrate magiclink
```

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

If the user tries to use an invalid magic token they will be shown a custom error page. To override the HTML for this page you can set the `MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME` setting. If you would like to return a 404 page you can set this setting to a empty string (or any falsy value). If you would like to redirect to another page (say a custom front-end) you can use the `MAGICLINK_LOGIN_FAILED_REDIRECT` setting.

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
    "logo_url": "https://example.com/logo.png",
    "background-colour": "#ffffff",
    "main-text-color": "#000000",
    "button-background-color": "#0078be",
    "button-text-color": "#ffffff",
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

*Note: Settings are read when they are used, so `override_settings` works in your tests. A bad value in `settings.py` raises `ImproperlyConfigured` when Django starts*

```python
# Override the login page template. See 'Login page' in the Setup section
MAGICLINK_LOGIN_TEMPLATE_NAME = "myapp/login.html"

# Override the login page template. See 'Login sent page' in the Setup section
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = "myapp/login_sent.html"

# Override the template that shows when the user tries to login with a
# magic link that is not valid. See 'Login failed page' in the Setup section
MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"

# If a login failed redirect is specified the user will be redirected to this
# URL instead of being shown the LOGIN_FAILED_TEMPLATE
MAGICLINK_LOGIN_FAILED_REDIRECT = ""

# If this setting is set to False a user account will be created the first time
# a user requests a login link.
MAGICLINK_REQUIRE_SIGNUP = True
# Override the login page template. See 'Login sent page' in the Setup section
MAGICLINK_SIGNUP_TEMPLATE_NAME = "myapp/signup.html"

# Set Djangos login redirect URL to be used once the user opens the magic link
# This will be used whenever a ?next parameter is not set on login
LOGIN_REDIRECT_URL = "/accounts/profile/"

# If a new user is created via the signup page use this setting to send them to
# a different url than LOGIN_REDIRECT_URL when clicking the magic link
# This will fall back to LOGIN_REDIRECT_URL
MAGICLINK_SIGNUP_LOGIN_REDIRECT = "/welcome/"

# Change the url a user is redirect to after requesting a magic link
MAGICLINK_LOGIN_SENT_REDIRECT = "magiclink:login_sent"

# Ensure the branding of the login email is correct. This setting is not needed
# if you override the `login_email.html` template
MAGICLINK_EMAIL_STYLES = {
    "logo_url": "",
    "background-colour": "#ffffff",
    "main-text-color": "#000000",
    "button-background-color": "#0078be",
    "button-text-color": "#ffffff",
}

# If you want to use your own email templates you can override the text and
# html templates used with:
MAGICLINK_EMAIL_TEMPLATE_NAME_TEXT = "myapp/login_email.text"
MAGICLINK_EMAIL_TEMPLATE_NAME_HTML = "myapp/login_email.html"

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

# Do not show if an email address has an account on the login and signup pages.
# See 'Account enumeration' in the Security section
MAGICLINK_PREVENT_ENUMERATION = False

# Override the default magic link length
# Warning: Overriding this setting has security implications, shorter tokens
# are much more susceptible to brute force attacks*
MAGICLINK_TOKEN_LENGTH = 50

# Require the user email to be included in the verification link
# Warning: If this is set to false tokens are more vulnerable to brute force
MAGICLINK_VERIFY_INCLUDE_EMAIL = True

# Show a page with a "Log in" button when the magic link is opened, and only log
# in when the button is pressed. See 'Email scanners' in the Security section
MAGICLINK_LOGIN_CONFIRM = False
MAGICLINK_LOGIN_CONFIRM_TEMPLATE_NAME = "magiclink/login_confirm.html"

# Ensure the user who clicked magic link used the same browser as the
# initial login request.
# Note: This can cause issues on devices where the default browser is
# different from the browser being used by the user such as on iOS)
MAGICLINK_REQUIRE_SAME_BROWSER = True

# Ensure the user who clicked magic link has the same IP address as the
# initial login request.
MAGICLINK_REQUIRE_SAME_IP = True

# Store only the network part of a client's IP address: the first 24 bits of
# an IPv4 address and the first 64 bits of an IPv6 address.
# Note: This has no effect if MAGICLINK_REQUIRE_SAME_IP as no IP address
# is stored
MAGICLINK_ANONYMIZE_IP = True

# The number of proxies in front of Django that add to the X-Forwarded-For
# header. The client IP is taken this many places from the right of the header.
# 0 ignores X-Forwarded-For and uses REMOTE_ADDR. See 'Proxies' in the
# Security section
MAGICLINK_TRUSTED_PROXY_COUNT = 0

# A header that your proxy or load balancer sets to the client IP address,
# for example "X-Real-IP". This is used before MAGICLINK_TRUSTED_PROXY_COUNT
MAGICLINK_TRUSTED_CLIENT_IP_HEADER = ""

# The number of times a login token can be used before being disabled
MAGICLINK_TOKEN_USES = 1

# How often a user can request a new login token (basic rate limiting).
# If the user asks again while their last magic link can still be used, the
# login page redirects to the login sent page and does not send a new email.
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
# How long a login or signup form is valid for after the page loads. An
# expired form is shown again with an error and can be sent again. It is not
# treated as spam. Do not cache the login and signup pages, otherwise the
# forms will expire
MAGICLINK_ANTISPAM_FORM_MAX_AGE = 21600  # In seconds - Default is 6 hours
# The name of the hidden field that must be left empty. If you change this,
# also change the CSS that hides its label (label[for="id_url"])
MAGICLINK_ANTISPAM_HONEYPOT_FIELD = "url"
# If a form fails the anti spam checks, redirect to the login sent page without
# sending an email, instead of showing an error that tells a bot what to change.
# A person who sends the form faster than MAGICLINK_ANTISPAM_FIELD_TIME allows,
# for example after their browser fills in the email address, also gets no email
MAGICLINK_ANTISPAM_QUIET_REJECT = False

# The scheme and domain used for the link in the login email, for example
# "https://example.com". If this is not set the domain comes from
# django.contrib.sites or the request's Host header. See 'Host header' in the
# Security section
MAGICLINK_SITE_URL = ""

# Limit requests by IP, by email and for the whole site. See 'Rate limits' in
# the Security section. There are no limits by default
MAGICLINK_RATE_LIMITS = {
    "request": "5/h/ip,3/10m/email",
    "request_site": "100/m",
    "verify_failed": "10/m/ip",
}

# Only allow email addresses from these domains, for example for an internal
# tool. Subdomains are included. An empty list allows all domains
MAGICLINK_ALLOWED_EMAIL_DOMAINS = []
# Do not allow email addresses from these domains, for example disposable mail
# domains. Subdomains are included. This is checked before the allowed list
MAGICLINK_BLOCKED_EMAIL_DOMAINS = []

# Use your own login and signup forms. See 'Custom forms'
MAGICLINK_FORMS = {
    "login": "myapp.forms.MyLoginForm",
    "signup": "myapp.forms.MySignupForm",
}

# Functions that can reject a request for a magic link. See 'Spam checks'
MAGICLINK_SPAM_CHECKS = ["myproject.checks.no_tor"]

# The class used to get the client IP, check login requests and send the login
# email. See 'Adapter'
MAGICLINK_ADAPTER = "magiclink.adapter.MagicLinkAdapter"

# Override the login verify address. You must inherit from Magiclink LoginVerify
# view. See Manual usage for more details
MAGICLINK_LOGIN_VERIFY_URL = "magiclink:login_verify"

# If an email address has been added to the unsubscribe table but is also
# assocaited with a Django user, should a login email be sent
MAGICLINK_IGNORE_UNSUBSCRIBE_IF_USER = False
```

## Magic Link cleanup

Each Magic Link is a seperate row in the database. To help give the user a better warning as to why their login was not successful, magic links are not cleared even once they have expired or have been disabled.

To clear old disabled magic links as well as magic links which expired over 1 week ago, you can use the `magiclink_clear_logins` management command

```
python manage.py magiclink_clear_logins
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
* A user whose `is_active` flag is False can not log in and is logged out of any existing session

*Note: Each of the above settings can be overridden / changed when configuring django-magiclink*

### Proxies

By default the client IP address comes from `REMOTE_ADDR` and the `X-Forwarded-For` header is ignored, because any client can send this header with any value. If Django runs behind a proxy or load balancer, `REMOTE_ADDR` is the address of the proxy. In this case, do one of the following:

* Set `MAGICLINK_TRUSTED_PROXY_COUNT` to the number of proxies that add to `X-Forwarded-For`. For example, use `1` for a single nginx server
* Set `MAGICLINK_TRUSTED_CLIENT_IP_HEADER` to a header that your proxy always sets and that clients can not set, for example `X-Real-IP`

If these settings are wrong, `MAGICLINK_REQUIRE_SAME_IP` compares the wrong address, or a client can choose the address it is given.

If neither setting is set, logins can fail behind a load balancer or CDN with more than one node, for example AWS ALB, Google Cloud load balancing, Cloudflare or Heroku. The request for a link and the click on it can reach Django through different nodes, so `REMOTE_ADDR` changes and `MAGICLINK_REQUIRE_SAME_IP` disables the link. A warning is logged once if a request has `X-Forwarded-For` and neither setting is set.

Some proxies add a port to the address, so `203.0.113.9:5678` is read as `203.0.113.9`. A value that is not an IP address is ignored and the next source is used.

If no IP address is found, a warning is logged and `MAGICLINK_REQUIRE_SAME_IP` has no address to compare, so the check passes if the link also has no address. For example, `REMOTE_ADDR` is empty if gunicorn runs on a unix socket. Set one of the settings above to use the check.

### Host header

If `MAGICLINK_SITE_URL` is not set and `django.contrib.sites` is not installed, the domain of the link in the login email comes from the request's `Host` header. If `ALLOWED_HOSTS` is `["*"]` or a broad wildcard, an attacker can request a login link for another person with `Host: evil.example`. That person then gets a real email with a link to the attacker's site, and the attacker gets the token when they click it.

Set `MAGICLINK_SITE_URL`, or set `ALLOWED_HOSTS` to only the domains your site uses.

### Account enumeration

By default the login page shows "We could not find a user with that email address" and the signup page shows "Email address is already linked to an account". Bots use these messages to build lists of real accounts.

Set `MAGICLINK_PREVENT_ENUMERATION = True` to hide this:

* The login and signup pages always redirect to the login sent page if the account is the reason a link can not be sent. This covers an unknown email address, a deactivated user and an email address on the unsubscribe list
* If someone signs up with the email address of an existing account, that account gets a login link. The account is not changed
* The same cookie is set and a `MagicLink` row is created in every case, so the response does not show which case it is. If no email is sent, the token in the row is never shown to anyone

If you use this setting, change your login sent page so it says "If there is an account for this email address we have sent you a magic link". The default template does this using the `{{ prevent_enumeration }}` context variable.

Sending an email takes time, so a slow response can still show that an email was sent. To stop this, send the email in the background (see 'Sending email in the background'). The `SignupFormWithUsername` and `SignupFormFull` forms still show if a username is in use.

### Email scanners

Outlook Safe Links, Proofpoint, Mimecast and similar tools open the links in an email before the user does. A scanner has a different IP address and does not have the same browser cookie, so the link is disabled and the user sees an error when they click it.

To stop this, set `MAGICLINK_LOGIN_CONFIRM = True`. Opening the link then shows a page with a "Log in" button and does not check or use the token. Only the POST from the button logs the user in, and scanners do not submit forms. This also stops a crafted link from logging a person in to an attacker's account without them pressing a button.

If you override `MAGICLINK_LOGIN_CONFIRM_TEMPLATE_NAME`, include the form below. It has no `action` so that it posts to the URL with the token. Do not load scripts or other files from other sites on this page.

```html
<form method="post">
    {% csrf_token %}
    <button type="submit">Log in</button>
</form>
```

### Rate limits

`MAGICLINK_LOGIN_REQUEST_TIME_LIMIT` limits how often one email address can ask for a link. It does not stop bots that enter many other people's addresses into your forms, so you should also set `MAGICLINK_RATE_LIMITS`. It is a dict of these rule sets:

| Name | What it counts | What happens over the limit |
|---|---|---|
| `request` | Every POST to the login and signup pages, including invalid forms | The form shows an error, or if `MAGICLINK_ANTISPAM_QUIET_REJECT` is on, the user is redirected to the login sent page. `spam_detected` is sent. No email is sent |
| `request_site` | Requests that pass the form and spam checks. This protects your email sending reputation | The same as `request` |
| `verify_failed` | Failed logins with a magic link | The login failed page is shown and the token is not checked. `login_failed` is sent with no `magiclink` |

Each rule set is a comma separated string of `count/period` or `count/period/key` rules:

* The period is a number and a unit, or only a unit: `s`, `m`, `h` or `d`. For example `h`, `10m`
* `ip` counts per IP address, using the adapter's `get_client_ip`. IPv4 addresses are grouped by /24 and IPv6 addresses by /64, because one person can often use a whole IPv6 /64. If no IP address is found, the rule is not used
* `email` counts per email address. The address is converted to lowercase and any `+tag` is removed, so `name+1@example.com` counts as `name@example.com`
* With no key, the rule counts for the whole site

Rate limits use Django's cache, with a fixed time window. All your workers must share the cache, so `LocMemCache` and `DummyCache` do not work in production.

Anyone can use up the limit for an email address, which stops the real owner getting a link until the window ends. Keep `email` limits low enough to stop abuse, but not so low that this is easy to do.

If you write your own views, use `hit`, `is_limited`, `ahit` and `ais_limited` from `magiclink.ratelimit`.

### System checks

django-magiclink adds these warnings to Django's system checks, which run with commands such as `migrate` and `runserver`. To turn one off, add its ID to `SILENCED_SYSTEM_CHECKS`.

| ID | Warning | Fix |
|---|---|---|
| `magiclink.W001` | `ALLOWED_HOSTS` is `["*"]` with no `MAGICLINK_SITE_URL` and no `django.contrib.sites` | See 'Host header' |
| `magiclink.W002` | `MAGICLINK_RATE_LIMITS` is set and the default cache is `LocMemCache` or `DummyCache` | Use a cache that all workers share |
| `magiclink.W003` | `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST` or `USE_X_FORWARDED_PORT` is set, the client IP address is used, and no proxy settings are set | See 'Proxies' |
| `magiclink.W004` | `MAGICLINK_TOKEN_LENGTH` is below 20 | Use a longer token |

### Redirects

The `?next` parameter on the login and signup pages and the logout URL is only used if it points to an allowed host (see Django's `ALLOWED_HOSTS` setting). This stops these URLs from being used to send users to another site.


## Unsubscribe / stopping email spam

Sadly bots like to go around the internet and fill out any forms they can with random email addresses that don't belong to them. Because of this, if an email is added to the `MagicLinkUnsubscribe` model they will no longer receive a login or welcome email, even if the email has a user associated with it. This behaviour can be changed for existing users using the `MAGICLINK_IGNORE_UNSUBSCRIBE_IF_USER` setting.

Adding a user to the unsubscribe model is done using the normal Django ORM create method

```python
from magiclink.models import MagicLinkUnsubscribe

MagicLinkUnsubscribe.objects.create(email="test@example.com")
```

If you are using the Django Magiclink login or signup functionality, the unsubscribe check happens during form validation. This means a new user will never be created if their email address has already been added to the `MagicLinkUnsubscribe` list.


## Manual usage

### Creating magiclinks

django-magiclink uses a model to help create, send and validate magic links. A `create_magiclink` helper function can be used easily create a MagicLink using the correct settings:

```python
from magiclink.helpers import create_magiclink

# Returns newly created from magiclink.models.MagicLink instance
magiclink = create_magiclink(email, request, redirect_url="")

# Generates the magic link url and sends it in an email
magiclink.send(request)

# If you want to build the magic link from the model instance but don't want to
#  send the email you can you can use:
magic_link_url = magiclink.generate_url(request)
```

### Custom forms

To add a field to the login or signup form, such as a captcha, subclass the form and set `MAGICLINK_FORMS`. You can also set `form_class` on a subclass of the `Login` or `Signup` view, or pass it to `as_view()`.

```python
from magiclink.forms import LoginForm, SignupForm

from myapp.fields import CaptchaField


class MyLoginForm(LoginForm):
    captcha = CaptchaField()


class MySignupForm(SignupForm):
    captcha = CaptchaField()
```

```python
MAGICLINK_FORMS = {
    "login": "myapp.forms.MyLoginForm",
    "signup": "myapp.forms.MySignupForm",
}
```

Your form must subclass one of the forms in `magiclink.forms`. If you set a custom signup form, the view uses it for every signup POST, whatever `form_name` is sent, and it is the value of all four signup form names in the template context.

### Custom Login verify flow

It is also possible to override the login verify flow to run your own code once the user has successfully logged in instead of a simple redirect. To do this you will need to create a new view which inherits the `magiclink.views.LoginVerify` view and overrides the `login_complete_action` method.

The below example will redirect the user to a different page depending on superuser / staff status:


Your own `views.py`

```python
from magiclink.views import LoginVerify


class CustomLoginVerify(LoginVerify):
    def login_complete_action(self):
        if self.request.user.is_superuser:
            url = reverse("superuser_page")
        elif self.request.user.is_staff:
            url = reverse("staff_page")
        else:
            url = reverse("normal_page")
        return HttpResponseRedirect(url)
```


Your own `urls.py`

```python
urlpatterns = [
    ...
    path(
        'custom-login-verify/',
        CustomLoginVerify.as_view(),
        name='custom_login_verify'
    ),
    ...
]
```


`settings.py`

```python
...
MAGICLINK_LOGIN_VERIFY_URL = "custom_login_verify"
...
```


### Async

The `MagicLinkBackend` authentication backend can be used with Django's async authentication functions such as `aauthenticate()`, `alogin()` and `request.auser()`. The django-magiclink views are synchronous but can be used with both WSGI and ASGI.

If you are writing your own async views, there are async versions of the helper functions and `MagicLink` methods:

```python
from magiclink.helpers import acreate_magiclink

# Returns a newly created magiclink.models.MagicLink instance
magiclink = await acreate_magiclink(email, request, redirect_url="")

# Generates the magic link url and sends it in an email
await magiclink.asend(request)
```

There is also `aget_or_create_user()` in `magiclink.helpers`, and `avalidate()`, `aused()` and `adisable()` on `MagicLink`. `asend()` calls the adapter's `asend_email()`. Django does not have an async email API, so by default this runs `send_email()` in a thread.


## Adapter

The adapter is one class that you can override to change how django-magiclink behaves. Subclass `magiclink.adapter.MagicLinkAdapter` and set `MAGICLINK_ADAPTER` to its path.

| Method | Default | Purpose |
|---|---|---|
| `get_client_ip(request)` | Uses `MAGICLINK_TRUSTED_PROXY_COUNT` and `MAGICLINK_TRUSTED_CLIENT_IP_HEADER` | Returns the client IP address |
| `check_request(request, email, form)` | Runs `MAGICLINK_SPAM_CHECKS` | Returns a reason to reject a request for a magic link, or `None`. The login and signup views call this after the form is valid |
| `send_email(magiclink, request)` | Sends the email with `send_mail` | Sends the login email |

`check_request` and `send_email` can do I/O, so they have async versions (`acheck_request` and `asend_email`). By default these call the sync method in a thread. The django-magiclink views are synchronous and call `check_request`. If you write your own async view, call `await get_adapter().acheck_request(request, email, form)` before `acreate_magiclink`.

If `check_request` returns a reason, `spam_detected` is sent and no email is sent. The form shows the reason as an error, or if `MAGICLINK_ANTISPAM_QUIET_REJECT` is on, the user is redirected to the login sent page.

Use the adapter for anything that changes behaviour or returns a value. Use [signals](#signals) for anything that only observes.

### Spam checks

`MAGICLINK_SPAM_CHECKS` is a list of paths to functions. Each function gets `(request, email, form)` and returns a reason string to reject the request, or `None`. The checks run in order and the first reason stops the request. This lets you add captcha checks, IP reputation services or anything else without a subclass of the adapter.

```python
# myproject/checks.py
from myproject.tor import is_tor_exit_node


def no_tor(request, email, form):
    if is_tor_exit_node(request.META["REMOTE_ADDR"]):
        return "Requests from Tor are not allowed"
    return None
```

If you override `check_request`, call `super().check_request(request, email, form)` to keep these checks.

### Sending email in the background

Override `send_email` to send the email with Django 6.0 Tasks, Celery, RQ or similar. Create the URL in `send_email`, because the task does not have the request:

```python
from magiclink.adapter import MagicLinkAdapter
from myapp.tasks import send_login_email


class MyAdapter(MagicLinkAdapter):
    def send_email(self, magiclink, request):
        send_login_email.delay(magiclink.pk, magiclink.generate_url(request))
```

```python
from magiclink.models import MagicLink


@shared_task
def send_login_email(magiclink_id, url):
    MagicLink.objects.get(pk=magiclink_id).deliver_email(url)
```


## Signals

django-magiclink sends these signals from `magiclink.signals`. Use them to log, count or alert on events. Each signal is sent with the `request`.

| Signal | Sender | Other arguments | Sent when |
|---|---|---|---|
| `magiclink_requested` | `MagicLink` | `magiclink` | A magic link is created |
| `magiclink_sent` | `MagicLink` | `magiclink` | The login email is sent, or passed to the task that sends it |
| `login_succeeded` | `MagicLinkBackend` | `user`, `magiclink` | A magic link is used to log in |
| `login_failed` | `MagicLinkBackend`, or `LoginVerify` over a rate limit | `magiclink`, `reason` | A magic link can not be used to log in. `magiclink` is `None` if no magic link has the token or the rate limit stopped the check |
| `spam_detected` | The login or signup view | `form`, `reason` | A form fails the anti spam checks, the adapter rejects the request or a rate limit is reached |

```python
from django.dispatch import receiver
from magiclink.signals import login_failed


@receiver(login_failed)
def log_failed_login(sender, request, magiclink, reason, **kwargs):
    print(f"Magic link login failed: {reason}")
```

## Upgrading

### Upgrading to 2.0.0

Version `2.0.0` does not add any new migrations or settings. If you upgrade from a previous version please note the following changes:

* Django 5.2 or above is required
* `packaging` is no longer installed as a dependency of django-magiclink
* If you have subclassed `MagicLinkBackend` and overridden `authenticate()` or `get_user()`, you will also need to override the matching async method (`aauthenticate()` or `aget_user()`). The async methods no longer call the sync methods

### Upgrading to 1.4.0

Version `1.4.0` does not add any new migrations or settings. If you upgrade from a previous version please note the following changes:

* Python 3.11 or above is required
* The magiclink models always use `AutoField` for their primary keys, whatever `DEFAULT_AUTO_FIELD` is set to. This stops Django 6 asking to create a new migration for magiclink. If you have already changed the magiclink tables to `BigAutoField` with your own migration (for example using `MIGRATION_MODULES`) you will need to subclass `magiclink.apps.MagiclinkConfig`, set `default_auto_field = "django.db.models.BigAutoField"` and use your subclass in `INSTALLED_APPS`
* The `?next` parameter on the signup page and the logout URL is ignored if it points to a different host. The user is sent to `MAGICLINK_SIGNUP_LOGIN_REDIRECT` or `LOGOUT_REDIRECT_URL` instead
* If the signup page is posted with a `form_name` which is not one of the four signup forms, the user is redirected back to the signup page
* If you have overridden the `login_email.txt` template, change `{{ magiclink }}` to `{{ magiclink|safe }}` otherwise the link in the plain text email will not work

### Upgrading to 1.2.0

A new migration was added to version `1.2.0`. If you upgrade to `1.2.0` or above from a previous version please ensure you migrate

```bash
python manage.py migrate magiclink
```


## Development

django-magiclink uses [uv](https://docs.astral.sh/uv/) to manage its dependencies and [tox](https://tox.wiki/) to run the tests against each supported version of Python and Django.

```bash
# Create a virtual environment with all of the development dependencies
uv sync

# Run the tests using the latest version of Django
uv run pytest

# Run the linting, type checks and tests for every supported version
uv run tox p

# Lint, format and type check the code
uv run ruff check --fix .
uv run ruff format .
uv run mypy magiclink

# Build the package
uv build
```

New versions are published to PyPI by GitHub Actions when a version tag such as `1.4.0` is pushed. The tag must match the version in `pyproject.toml`.
