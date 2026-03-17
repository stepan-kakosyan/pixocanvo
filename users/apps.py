from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

    def ready(self):
        # Ensure profile records are auto-created/updated with users.
        from . import signals  # noqa: F401
