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
    pending_email = models.EmailField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"


class ContactMessage(models.Model):
    STATUS_RECEIVED = "RECEIVED"
    STATUS_REVIEWED = "REVIEWED"
    STATUS_WATCHING = "WATCHING"
    STATUS_CHOICES = (
        (STATUS_RECEIVED, "Received"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_WATCHING, "Watching"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="contact_messages",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    description = models.TextField(max_length=5000)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_RECEIVED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"ContactMessage<{self.email}:{self.subject[:32]}>"
