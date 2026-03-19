from django.contrib import admin

from .models import ContactMessage, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "avatar")
    search_fields = ("user__username", "user__email")


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
