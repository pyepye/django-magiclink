from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUserEmailOnly(AbstractUser):
    username = None
    email = models.EmailField('email address', unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = models.Manager()

    def __str__(self):
        return self.email


class CustomUserFullName(CustomUserEmailOnly):
    full_name = models.TextField()


class CustomUserName(CustomUserEmailOnly):
    name = models.TextField()
