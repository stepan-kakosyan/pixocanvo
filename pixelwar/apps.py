from django.apps import AppConfig


class PixelwarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pixelwar"

    def ready(self):
        # Register signal handlers for image optimization and cleanup
        from . import signals  # noqa: F401
