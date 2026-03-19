from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.templatetags.static import static
from django.utils import timezone

from .models import Notification


def _initials_from_name(value: str, fallback: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        return fallback
    return cleaned[:1].upper()


def system_notification_visual() -> dict:
    return {
        "visual_type": Notification.VISUAL_SYSTEM,
        "image_url": static("pixelwar/images/logo-bg.png"),
        "initials": "PC",
    }


def user_notification_visual(user) -> dict:
    profile = getattr(user, "profile", None)
    return {
        "visual_type": Notification.VISUAL_USER,
        "image_url": (
            profile.avatar.url if profile and getattr(profile, "avatar", None) else ""
        ),
        "initials": _initials_from_name(getattr(user, "username", ""), "U"),
    }


def community_notification_visual(community) -> dict:
    return {
        "visual_type": Notification.VISUAL_COMMUNITY,
        "image_url": community.image.url if getattr(community, "image", None) else "",
        "initials": _initials_from_name(getattr(community, "name", ""), "C"),
    }


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "title": notification.title,
        "body": notification.body,
        "target_url": notification.target_url,
        "is_read": notification.is_read,
        "visual_type": notification.visual_type,
        "image_url": notification.image_url,
        "initials": notification.initials,
        "created_at": notification.created_at.isoformat(),
        "created_at_label": timezone.localtime(notification.created_at).strftime(
            "%Y-%m-%d %H:%M"
        ),
    }


def unread_count_for_user(user_id: int) -> int:
    return Notification.objects.filter(recipient_id=user_id, is_read=False).count()


def push_notification_event(user_id: int, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"notifications_user_{user_id}",
        {
            "type": "notification_message",
            "payload": payload,
        },
    )


def create_notification(
    *,
    recipient_id: int,
    notification_type: str,
    title: str,
    body: str,
    target_url: str,
    visual_type: str = Notification.VISUAL_SYSTEM,
    image_url: str = "",
    initials: str = "PC",
) -> Notification:
    notification = Notification.objects.create(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        body=body,
        target_url=target_url,
        visual_type=visual_type,
        image_url=image_url,
        initials=initials,
    )
    push_notification_event(
        recipient_id,
        {
            "event": "notification.created",
            "notification": serialize_notification(notification),
            "unread_count": unread_count_for_user(recipient_id),
        },
    )
    return notification
