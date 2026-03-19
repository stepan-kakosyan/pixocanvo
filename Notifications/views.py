from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Notification
from .services import push_notification_event, unread_count_for_user


def _avatar_url_for_request_user(request: HttpRequest) -> str:
    if not request.user.is_authenticated:
        return ""
    profile = getattr(request.user, "profile", None)
    if profile and profile.avatar:
        return profile.avatar.url
    return ""


def _base_context(request: HttpRequest) -> dict:
    return {
        "layout": (
            "partial" if request.headers.get("HX-Request") == "true" else "full"
        ),
        "active_tab": None,
        "avatar_url": _avatar_url_for_request_user(request),
        "current_community": None,
    }


@login_required
def notification_list(request: HttpRequest) -> HttpResponse:
    notifications = list(
        Notification.objects.filter(recipient=request.user).order_by(
            "-created_at",
            "-id",
        )
    )
    unread_count = sum(0 if notification.is_read else 1 for notification in notifications)
    context = {
        **_base_context(request),
        "notifications": notifications,
        "unread_count": unread_count,
    }
    return render(request, "Notifications/notifications_list.html", context)


@login_required
def open_notification(request: HttpRequest, notification_id: int) -> HttpResponse:
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        push_notification_event(
            request.user.id,
            {
                "event": "notification.read",
                "notification_id": notification.id,
                "unread_count": unread_count_for_user(request.user.id),
            },
        )
    if notification.target_url:
        return redirect(notification.target_url)
    return redirect("notifications:list")


@login_required
def mark_notification_read(request: HttpRequest, notification_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        push_notification_event(
            request.user.id,
            {
                "event": "notification.read",
                "notification_id": notification.id,
                "unread_count": unread_count_for_user(request.user.id),
            },
        )
    return JsonResponse({"ok": True})


@login_required
def mark_all_notifications_read(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("notifications:list")
    next_url = str(request.POST.get("next", "")).strip()
    updated = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True, read_at=timezone.now())
    if updated:
        push_notification_event(
            request.user.id,
            {
                "event": "notification.read_all",
                "unread_count": 0,
            },
        )
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(status=200)
    if next_url:
        return redirect(next_url)
    return redirect("notifications:list")
