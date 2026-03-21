"""Signal handlers for pixelwar models."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from utils.image_utils import (
    cleanup_storage_prefix,
    create_thumbnail,
    delete_image_file,
    optimize_image,
)
from .models import Community


@receiver(pre_save, sender=Community)
def cleanup_community_image_on_update(
    sender, instance: Community, **kwargs
) -> None:
    """Handle update flow: cleanup, optimize, and thumbnail generation."""
    if not instance.pk:
        return

    try:
        old_instance = Community.objects.get(pk=instance.pk)
    except Community.DoesNotExist:
        return

    if instance.image:
        if instance.image._committed:
            return

        if old_instance.image:
            delete_image_file(old_instance.image)
        if old_instance.image_thumbnail:
            delete_image_file(old_instance.image_thumbnail)

        optimized = optimize_image(instance.image, max_width=750, quality=85)
        thumbnail = create_thumbnail(instance.image, size=200, quality=85)

        instance.image.save("cover.jpg", optimized, save=False)
        instance.image_thumbnail.save("cover.jpg", thumbnail, save=False)
        return

    if old_instance.image:
        delete_image_file(old_instance.image)
    if old_instance.image_thumbnail:
        delete_image_file(old_instance.image_thumbnail)
    instance.image_thumbnail = None


@receiver(post_save, sender=Community)
def optimize_community_image(
    sender, instance: Community, created: bool, **kwargs
) -> None:
    """Handle create flow where community id is not available pre-save."""
    if not created or not instance.image:
        return
    if instance.image_thumbnail:
        return

    original_uploaded = instance.image

    optimized = optimize_image(instance.image, max_width=750, quality=85)
    thumbnail = create_thumbnail(instance.image, size=200, quality=85)

    instance.image.save("cover.jpg", optimized, save=False)
    instance.image_thumbnail.save("cover.jpg", thumbnail, save=False)

    Community.objects.filter(pk=instance.pk).update(
        image=instance.image,
        image_thumbnail=instance.image_thumbnail,
    )

    if original_uploaded and original_uploaded.name != instance.image.name:
        delete_image_file(original_uploaded)


@receiver(post_save, sender=Community)
def cleanup_community_image_folder(
    sender, instance: Community, **kwargs
) -> None:
    """Remove stale community cover files from storage prefix."""
    prefix = f"community_covers/{instance.pk}"
    storage = None
    keep_paths = []

    if instance.image:
        storage = instance.image.storage
        keep_paths.append(instance.image.name)
    if instance.image_thumbnail:
        storage = instance.image_thumbnail.storage
        keep_paths.append(instance.image_thumbnail.name)

    if storage is None:
        return

    cleanup_storage_prefix(storage, prefix, keep_paths=keep_paths)
