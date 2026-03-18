from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        # Ensure signal handlers are registered when Django boots.
        from . import signals  # noqa: F401
