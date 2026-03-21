from django.core.management.base import BaseCommand

from pixelwar.models import Community
from users.models import UserProfile
from utils.image_utils import cleanup_storage_prefix


class Command(BaseCommand):
    help = "Remove stale avatar/community image files and keep only active files"

    def handle(self, *args, **options):
        user_deleted = 0
        community_deleted = 0

        for profile in UserProfile.objects.all().iterator(chunk_size=200):
            storage = None
            keep_paths = []
            prefix = f"profile-avatars/{profile.user_id}"

            if profile.avatar:
                storage = profile.avatar.storage
                keep_paths.append(profile.avatar.name)
            if profile.avatar_thumbnail:
                storage = profile.avatar_thumbnail.storage
                keep_paths.append(profile.avatar_thumbnail.name)
            if storage is None:
                continue

            user_deleted += cleanup_storage_prefix(
                storage,
                prefix,
                keep_paths=keep_paths,
            )

        for community in Community.objects.all().iterator(chunk_size=200):
            storage = None
            keep_paths = []
            prefix = f"community_covers/{community.pk}"

            if community.image:
                storage = community.image.storage
                keep_paths.append(community.image.name)
            if community.image_thumbnail:
                storage = community.image_thumbnail.storage
                keep_paths.append(community.image_thumbnail.name)
            if storage is None:
                continue

            community_deleted += cleanup_storage_prefix(
                storage,
                prefix,
                keep_paths=keep_paths,
            )

        total_deleted = user_deleted + community_deleted
        self.stdout.write(
            self.style.SUCCESS(
                "Cleanup complete. "
                f"Deleted {total_deleted} stale files "
                f"(avatars: {user_deleted}, communities: {community_deleted})."
            )
        )
