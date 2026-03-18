from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    email_confirmed = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"
