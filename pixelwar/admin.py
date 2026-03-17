from django.contrib import admin

from .models import ChatMessage, Community, CommunityMembership, Pixel, UserAction


class CommunityMembershipInline(admin.TabularInline):
    model = CommunityMembership
    extra = 0
    readonly_fields = ("joined_at", "left_at")
    fields = ("user", "active", "joined_at", "left_at")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "member_count", "created_at")
    list_select_related = ("owner",)
    search_fields = ("name", "slug", "owner__username")
    readonly_fields = ("invite_token", "created_at")
    inlines = [CommunityMembershipInline]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.memberships.filter(active=True).count()


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "community", "active", "joined_at", "left_at")
    list_filter = ("active",)
    search_fields = ("user__username", "community__name", "community__slug")
    list_select_related = ("user", "community")


@admin.register(Pixel)
class PixelAdmin(admin.ModelAdmin):
    list_display = ("x", "y", "color", "updated_at")
    search_fields = ("x", "y", "color")


@admin.register(UserAction)
class UserActionAdmin(admin.ModelAdmin):
    list_display = ("user_key", "x", "y", "color", "accepted", "created_at")
    list_filter = ("accepted", "created_at")
    search_fields = ("user_key", "ip_address")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at")
    search_fields = ("user__username", "message")
    list_filter = ("created_at",)
