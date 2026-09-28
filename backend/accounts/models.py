from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class Profile(models.Model):
    AVATAR_CHOICES = [
        ('knight-1', 'Knight 1'),
        ('knight-2', 'Knight 2'),
        ('knight-3', 'Knight 3'),
        ('knight-4', 'Knight 4'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    nickname = models.CharField(max_length=30, unique=True)
    avatar_key = models.CharField(max_length=30, default="knight-1")

    def __str__(self):
        return f"{self.nickname} ({self.user.username})"
