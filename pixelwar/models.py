import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import User
from django.db import models


class Community(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_communities",
    )
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"Community<{self.slug}>"


class CommunityMembership(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"],
                name="uniq_community_member",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} in {self.community.slug}"


class Pixel(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="pixels",
    )
    x = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    y = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)]
    )
    color = models.CharField(max_length=7, default="#FFFFFF")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["community", "x", "y"],
                name="uniq_pixel_coord_in_community",
            ),
        ]
        indexes = [
            models.Index(fields=["community", "x", "y"]),
        ]

    def __str__(self) -> str:
        return f"Pixel({self.x}, {self.y})={self.color}"


class UserAction(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    user_key = models.CharField(max_length=128, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    x = models.PositiveIntegerField()
    y = models.PositiveIntegerField()
    color = models.CharField(max_length=7)
    accepted = models.BooleanField(default=False)
    rejection_reason = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["community", "user_key", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_key} ({self.x}, {self.y}) {self.color}"


class ChatMessage(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.message[:30]}"
