from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    TYPE_SYSTEM_NOTICE = "system_notice"
    TYPE_EMAIL_CONFIRMED = "email_confirmed"
    TYPE_JOIN_REQUEST = "join_request"
    TYPE_JOIN_APPROVED = "join_approved"
    TYPE_JOIN_DECLINED = "join_declined"
    VISUAL_SYSTEM = "system"
    VISUAL_USER = "user"
    VISUAL_COMMUNITY = "community"
    TYPE_CHOICES = (
        (TYPE_SYSTEM_NOTICE, "System notice"),
        (TYPE_EMAIL_CONFIRMED, "Email confirmed"),
        (TYPE_JOIN_REQUEST, "Join request"),
        (TYPE_JOIN_APPROVED, "Join approved"),
        (TYPE_JOIN_DECLINED, "Join declined"),
    )
    VISUAL_CHOICES = (
        (VISUAL_SYSTEM, "System"),
        (VISUAL_USER, "User"),
        (VISUAL_COMMUNITY, "Community"),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=255)
    target_url = models.CharField(max_length=255, blank=True, default="")
    visual_type = models.CharField(
        max_length=16,
        choices=VISUAL_CHOICES,
        default=VISUAL_SYSTEM,
    )
    image_url = models.CharField(max_length=255, blank=True, default="")
    initials = models.CharField(max_length=4, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Notification<{self.recipient.username}:{self.title}>"
