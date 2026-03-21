import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


def community_image_upload_path(instance, filename):
    """Store optimized community cover at community folder root."""
    community_name = slugify(instance.name) or f"community-{instance.pk or 'new'}"
    return f"community_covers/{instance.pk or 'new'}/{community_name}.jpg"


def community_image_thumbnail_upload_path(instance, filename):
    """Store community thumbnail in tmb subfolder."""
    community_name = slugify(instance.name) or f"community-{instance.pk or 'new'}"
    return (
        f"community_covers/{instance.pk or 'new'}/tmb/{community_name}.jpg"
    )


class Community(models.Model):
    MAX_MEMBER_CHOICES = (
        (5, "5"),
        (10, "10"),
        (20, "20"),
        (30, "30"),
        (50, "50"),
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_communities",
    )
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=280, blank=True, default="")
    slug = models.SlugField(max_length=80, unique=True)
    image = models.ImageField(
        upload_to=community_image_upload_path,
        blank=True,
        null=True,
    )
    image_thumbnail = models.ImageField(
        upload_to=community_image_thumbnail_upload_path,
        blank=True,
        null=True,
    )
    is_public = models.BooleanField(default=False)
    max_members = models.PositiveSmallIntegerField(
        choices=MAX_MEMBER_CHOICES,
        default=50,
    )
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"Community<{self.slug}>"


class CommunityJoinRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DECLINED, "Declined"),
    )

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_join_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"],
                name="uniq_join_request_per_user_community",
            ),
        ]
        indexes = [
            models.Index(fields=["community", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.community.slug} ({self.status})"


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
