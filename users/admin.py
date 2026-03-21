from django.contrib import admin

from .models import ContactMessage, PixoTransaction, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "avatar", "pixo_balance", "rewarded_pixels_count")
    search_fields = ("user__username", "user__email")


@admin.register(PixoTransaction)
class PixoTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "amount",
        "reason",
        "created_at",
    )
    search_fields = ("profile__user__username", "profile__user__email", "context_key")
    list_filter = ("reason", "created_at")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "subject",
        "name",
        "email",
        "user",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "subject", "description")
    readonly_fields = (
        "user",
        "name",
        "email",
        "subject",
        "description",
        "created_at",
        "updated_at",
    )
    fields = (
        "status",
        "user",
        "name",
        "email",
        "subject",
        "description",
        "created_at",
        "updated_at",
    )
