from .models import Notification


def notification_center(request):
    if not request.user.is_authenticated:
        return {
            "header_notifications": [],
            "header_notifications_unread_count": 0,
        }

    latest_notifications = list(
        Notification.objects.filter(recipient=request.user).order_by(
            "-created_at",
            "-id",
        )[:10]
    )
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return {
        "header_notifications": latest_notifications,
        "header_notifications_unread_count": unread_count,
    }
