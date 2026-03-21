from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


def avatar_upload_path(instance, filename):
    """Store optimized avatar at user folder root."""
    username = slugify(instance.user.username) or f"user-{instance.user_id}"
    return f"profile-avatars/{instance.user_id}/{username}.jpg"


def avatar_thumbnail_upload_path(instance, filename):
    """Store avatar thumbnail in tmb subfolder."""
    username = slugify(instance.user.username) or f"user-{instance.user_id}"
    return f"profile-avatars/{instance.user_id}/tmb/{username}.jpg"


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path, blank=True, null=True
    )
    avatar_thumbnail = models.ImageField(
        upload_to=avatar_thumbnail_upload_path, blank=True, null=True
    )
    email_confirmed = models.BooleanField(default=False)
    pending_email = models.EmailField(blank=True, null=True)
    pixo_balance = models.PositiveIntegerField(default=0)
    rewarded_pixels_count = models.PositiveIntegerField(default=0)
    acceleration_active = models.BooleanField(default=False)
    acceleration_pixels_placed = models.PositiveIntegerField(default=0)

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


class PixoTransaction(models.Model):
    REASON_EMAIL_VERIFIED = "email_verified"
    REASON_PIXEL_MILESTONE = "pixel_milestone"
    REASON_REFERRAL_COMMUNITY_JOIN = "referral_community_join"
    REASON_REFERRAL_MILESTONE = "referral_milestone"
    REASON_FEATURE_SPEND = "feature_spend"
    REASON_MANUAL_ADJUSTMENT = "manual_adjustment"
    REASON_CHOICES = (
        (REASON_EMAIL_VERIFIED, "Email verified"),
        (REASON_PIXEL_MILESTONE, "Pixel milestone"),
        (REASON_REFERRAL_COMMUNITY_JOIN, "Referral community join"),
        (REASON_REFERRAL_MILESTONE, "Referral milestone"),
        (REASON_FEATURE_SPEND, "Feature spend"),
        (REASON_MANUAL_ADJUSTMENT, "Manual adjustment"),
    )

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="pixo_transactions",
    )
    amount = models.IntegerField()
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    context_key = models.CharField(max_length=128, unique=True)
    details = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return (
            f"PixoTransaction<user={self.profile.user_id}, amount={self.amount}, "
            f"reason={self.reason}>"
        )


class ReferralAttribution(models.Model):
    SOURCE_COMMUNITY_INVITE = "community_invite"
    SOURCE_PERSONAL_LINK = "personal_link"
    SOURCE_CHOICES = (
        (SOURCE_COMMUNITY_INVITE, "Community invite"),
        (SOURCE_PERSONAL_LINK, "Personal link"),
    )

    referred_user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="referral_attribution",
    )
    referrer_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referred_users",
    )
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    community = models.ForeignKey(
        "pixelwar.Community",
        on_delete=models.SET_NULL,
        related_name="referral_attributions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    milestone_10_rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["referrer_user"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"ReferralAttribution<referred={self.referred_user_id}, "
            f"referrer={self.referrer_user_id}, source={self.source}>"
        )
