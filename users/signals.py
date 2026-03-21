from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from utils.image_utils import (
    cleanup_storage_prefix,
    create_thumbnail,
    delete_image_file,
    optimize_image,
)
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created: bool, **kwargs) -> None:
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance: User, **kwargs) -> None:
    # Keep profile row in sync for users created outside normal flow.
    UserProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=UserProfile)
def optimize_and_cleanup_avatar(
    sender, instance: UserProfile, **kwargs
) -> None:
    """Keep only optimized avatar + thumbnail and remove replaced files."""
    old_avatar = None
    old_thumbnail = None

    if instance.pk:
        try:
            old_instance = UserProfile.objects.get(pk=instance.pk)
            old_avatar = old_instance.avatar
            old_thumbnail = old_instance.avatar_thumbnail
        except UserProfile.DoesNotExist:
            pass

    if not instance.avatar:
        if old_avatar:
            delete_image_file(old_avatar)
        if old_thumbnail:
            delete_image_file(old_thumbnail)
        instance.avatar_thumbnail = None
        return

    needs_path_normalization = False
    if instance.avatar and instance.avatar.name:
        avatar_root = f"profile-avatars/{instance.user_id}/"
        if not instance.avatar.name.startswith(avatar_root):
            needs_path_normalization = True
        if "/original/" in instance.avatar.name:
            needs_path_normalization = True
    if not instance.avatar_thumbnail:
        needs_path_normalization = True
    elif "/tmb/" not in instance.avatar_thumbnail.name:
        needs_path_normalization = True

    should_rewrite = instance.avatar and (
        (not instance.avatar._committed) or needs_path_normalization
    )

    if should_rewrite:
        source_from_existing = bool(
            instance.avatar._committed and needs_path_normalization
        )

        # For new uploads, remove previous files first to keep deterministic
        # filenames. For legacy normalization, we must keep source available.
        if not source_from_existing:
            if old_avatar:
                delete_image_file(old_avatar)
            if old_thumbnail:
                delete_image_file(old_thumbnail)

        optimized = optimize_image(instance.avatar, max_width=750, quality=85)
        thumbnail = create_thumbnail(instance.avatar, size=200, quality=85)

        instance.avatar.save("avatar.jpg", optimized, save=False)
        instance.avatar_thumbnail.save("avatar.jpg", thumbnail, save=False)

        if source_from_existing:
            if old_avatar and old_avatar.name != instance.avatar.name:
                delete_image_file(old_avatar)
            if (
                old_thumbnail
                and old_thumbnail.name != instance.avatar_thumbnail.name
            ):
                delete_image_file(old_thumbnail)


@receiver(post_save, sender=UserProfile)
def cleanup_avatar_folder(sender, instance: UserProfile, **kwargs) -> None:
    """Remove stale avatar files from storage prefix, keep only current two."""
    prefix = f"profile-avatars/{instance.user_id}"
    storage = None
    keep_paths = []

    if instance.avatar:
        storage = instance.avatar.storage
        keep_paths.append(instance.avatar.name)
    if instance.avatar_thumbnail:
        storage = instance.avatar_thumbnail.storage
        keep_paths.append(instance.avatar_thumbnail.name)

    if storage is None:
        return

    cleanup_storage_prefix(storage, prefix, keep_paths=keep_paths)
