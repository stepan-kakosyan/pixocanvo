from django.core.management.base import BaseCommand
from django.db import transaction

from pixelwar.models import Pixel


class Command(BaseCommand):
    help = "Delete all pixels from the canvas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt and delete all pixels.",
        )

    def handle(self, *args, **options):
        skip_confirm = options["yes"]
        total = Pixel.objects.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No pixels to delete."))
            return

        if not skip_confirm:
            self.stdout.write(
                f"This will delete {total} pixels. Type 'yes' to continue: "
            )
            user_input = input().strip().lower()
            if user_input != "yes":
                self.stdout.write(self.style.WARNING("Aborted. No pixels were deleted."))
                return

        with transaction.atomic():
            deleted_count, _ = Pixel.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted_count} pixel rows.")
        )
