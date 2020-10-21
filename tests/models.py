from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUserEmailOnly(AbstractUser):
    email = models.EmailField('email address', unique=True)


class CustomUserFullName(CustomUserEmailOnly):
    full_name = models.TextField()


class CustomUserName(CustomUserEmailOnly):
    name = models.TextField()
