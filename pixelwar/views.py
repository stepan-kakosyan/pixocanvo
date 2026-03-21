import json
import math
import re
import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Max, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from Notifications import signals as notification_signals
from django.views.decorators.http import require_GET, require_POST
from django_redis import get_redis_connection
from kafka.errors import KafkaError, NoBrokersAvailable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .kafka_producer import enqueue_chat_message, enqueue_pixel_update
from .models import ChatMessage, Community, CommunityJoinRequest
from .models import CommunityMembership, Pixel, UserAction

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_OWNED_COMMUNITIES = 5


def _channel_group_send(group: str, message: dict) -> None:
    """Synchronously send a message to a channel layer group."""
    async_to_sync(get_channel_layer().group_send)(group, message)


@require_GET
def switch_language(request: HttpRequest) -> HttpResponse:
    lang = str(request.GET.get("lang", "")).strip().lower()
    next_url = str(request.GET.get("next_url", "/")).strip()
    supported = {
        str(code).lower() for code, _name in getattr(settings, "LANGUAGES", [])
    }
    if lang not in supported:
        lang = str(getattr(settings, "LANGUAGE_CODE", "en")).split("-")[0]

    target = "/"
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = next_url

    translated_target = translate_url(target, lang)
    if translated_target:
        target = translated_target

    translation.activate(lang)
    response = redirect(target)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=365 * 24 * 60 * 60,
        path="/",
        samesite="Lax",
    )
    return response


def _avatar_url_for_request_user(request: HttpRequest) -> str:
    if not request.user.is_authenticated:
        return ""
    profile = getattr(request.user, "profile", None)
    return _avatar_url_from_profile(profile)


def _avatar_url_from_profile(profile) -> str:
    if not profile:
        return ""
    if profile.avatar_thumbnail:
        return profile.avatar_thumbnail.url
    if profile.avatar:
        return profile.avatar.url
    return ""


def _community_urls(community: Community | None) -> dict:
    return {
        "canvas_url": "/",
        "leaders_url": "/leaders/",
        "guide_url": "/guide/",
        "communities_url": "/communities/",
    }


def _base_nav_context(request: HttpRequest, active_tab: str | None,
                      community: Community | None) -> dict:
    data = {
        "avatar_url": _avatar_url_for_request_user(request),
        "active_tab": active_tab,
        "current_community": community,
        "layout": (
            "partial"
            if request.headers.get("HX-Request") == "true"
            else "full"
        ),
    }
    data.update(_community_urls(community))
    return data


def _dynamic_grid_settings() -> tuple[int, int, float, int]:
    initial = max(20, int(getattr(settings, "INITIAL_GRID_SIZE", 200)))
    step = max(1, int(getattr(settings, "GRID_EXPAND_STEP", 20)))
    threshold = float(getattr(settings, "GRID_FILL_EXPAND_THRESHOLD", 0.8))
    if threshold <= 0 or threshold >= 1:
        threshold = 0.8
    max_size = max(initial, int(getattr(settings, "GRID_MAX_SIZE", 1000)))
    return initial, step, threshold, max_size


def _grid_size_for_pixel_count(pixel_count: int) -> int:
    initial, step, threshold, max_size = _dynamic_grid_settings()
    size = initial
    filled = max(0, int(pixel_count))
    while size < max_size:
        expand_at = math.ceil((size * size) * threshold)
        if filled < expand_at:
            break
        size = min(size + step, max_size)
    return size


def _ensure_grid_covers_max_coord(size: int, max_coord: int) -> int:
    initial, step, _threshold, max_size = _dynamic_grid_settings()
    if max_coord < 0:
        return size
    required = max_coord + 1
    candidate = max(size, initial)
    while candidate < required and candidate < max_size:
        candidate = min(candidate + step, max_size)
    return candidate


def _grid_metrics_for_state(pixel_count: int, max_coord: int = -1) -> dict:
    size = _grid_size_for_pixel_count(pixel_count)
    size = _ensure_grid_covers_max_coord(size, max_coord)
    total_cells = size * size
    ratio = 0.0
    if total_cells > 0:
        ratio = min(1.0, max(0.0, pixel_count / total_cells))
    return {
        "grid_size": size,
        "filled_pixels": max(0, int(pixel_count)),
        "fill_ratio": round(ratio, 4),
    }


def _current_grid_metrics(community: Community) -> dict:
    aggregate = Pixel.objects.filter(community=community).aggregate(
        max_x=Max("x"),
        max_y=Max("y"),
    )
    max_x = aggregate.get("max_x")
    max_y = aggregate.get("max_y")
    max_coord = max(
        int(max_x) if max_x is not None else -1,
        int(max_y) if max_y is not None else -1,
    )
    pixel_count = Pixel.objects.filter(community=community).count()
    return _grid_metrics_for_state(pixel_count, max_coord=max_coord)


def _top_users_by_pixels(community: Community, limit: int = 10) -> list[dict]:
    rows = (
        UserAction.objects.filter(
            community=community,
            accepted=True,
            user_key__startswith="user:",
        )
        .values("user_key")
        .annotate(pixel_count=Count("id"))
        .order_by("-pixel_count")[: limit * 2]
    )
    counts_by_id: dict[int, int] = {}
    for row in rows:
        parts = str(row["user_key"]).split(":", 1)
        if len(parts) != 2:
            continue
        try:
            user_id = int(parts[1])
        except ValueError:
            continue
        counts_by_id[user_id] = int(row["pixel_count"])
    if not counts_by_id:
        return []
    users = User.objects.filter(id__in=counts_by_id.keys()).select_related("profile")
    user_info = {}
    for user in users:
        profile = getattr(user, "profile", None)
        user_info[user.id] = {
            "username": user.username,
            "avatar_url": _avatar_url_from_profile(profile),
        }
    top = []
    for user_id, pixel_count in counts_by_id.items():
        info = user_info.get(user_id)
        if info:
            top.append({
                "username": info["username"],
                "avatar_url": info["avatar_url"],
                "pixel_count": pixel_count,
            })
    top.sort(key=lambda item: item["pixel_count"], reverse=True)
    return top[:limit]


def _client_ip(request: HttpRequest) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_key(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    if not request.session.session_key:
        request.session.create()
    ip_address = _client_ip(request) or "unknown"
    return f"anon:{request.session.session_key}:{ip_address}"


def _community_for_user(user, slug: str) -> Community | None:
    if slug == "global":
        return None
    if not user.is_authenticated:
        return None
    return (
        Community.objects.filter(
            slug=slug,
            memberships__user=user,
            memberships__active=True,
        )
        .distinct()
        .first()
    )


def _display_name_for_user(user) -> str:
    full_name = str(getattr(user, "first_name", "") or "").strip()
    if full_name:
        return full_name
    return str(getattr(user, "username", "") or "User")


def _user_can_use_chat(user) -> bool:
    if not user.is_authenticated:
        return False
    profile = getattr(user, "profile", None)
    return bool(profile and profile.email_confirmed)


def _non_global_memberships_for_user(user) -> list[CommunityMembership]:
    if not user.is_authenticated:
        return []
    return list(
        CommunityMembership.objects.filter(
            user=user,
            active=True,
        )
        .exclude(community__slug__iexact="global")
        .select_related("community")
        .order_by("community__name")
    )


def _owned_communities_count_for_user(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    return Community.objects.filter(owner=user).exclude(slug="global").count()


def _community_active_member_count(community: Community) -> int:
    return CommunityMembership.objects.filter(
        community=community,
        active=True,
    ).count()


def _is_public_community_full(community: Community) -> bool:
    if not community.is_public:
        return False
    return _community_active_member_count(community) >= community.max_members


def _public_communities_for_lobby(user) -> list[dict]:
    communities = list(
        Community.objects.filter(is_public=True)
        .exclude(slug="global")
        .select_related("owner")
        .order_by("name")
    )
    if not communities:
        return []

    community_ids = [c.id for c in communities]
    member_counts = dict(
        CommunityMembership.objects.filter(
            community_id__in=community_ids,
            active=True,
        )
        .values("community_id")
        .annotate(total=Count("id"))
        .values_list("community_id", "total")
    )

    member_community_ids: set[int] = set()
    pending_request_ids: set[int] = set()
    if user.is_authenticated:
        member_community_ids = set(
            CommunityMembership.objects.filter(
                user=user,
                active=True,
                community_id__in=community_ids,
            ).values_list("community_id", flat=True)
        )
        pending_request_ids = set(
            CommunityJoinRequest.objects.filter(
                user=user,
                status=CommunityJoinRequest.STATUS_PENDING,
                community_id__in=community_ids,
            ).values_list("community_id", flat=True)
        )

    rows: list[dict] = []
    for community in communities:
        active_count = int(member_counts.get(community.id, 0))
        is_full = active_count >= int(community.max_members)
        is_member = community.id in member_community_ids
        is_pending = community.id in pending_request_ids
        can_request = (
            user.is_authenticated
            and community.owner_id != getattr(user, "id", None)
            and not is_member
            and not is_pending
            and not is_full
        )
        rows.append({
            "community": community,
            "active_count": active_count,
            "is_full": is_full,
            "is_member": is_member,
            "is_pending": is_pending,
            "can_request": can_request,
        })

    return rows


def _global_community(request: HttpRequest) -> Community | None:
    community = Community.objects.filter(slug="global").first()
    if community:
        return community
    community = Community.objects.order_by("id").first()
    if community:
        return community
    if request.user.is_authenticated:
        return Community.objects.create(owner=request.user,
                                        name="Global", slug="global")
    return None


def _join_community(user, community: Community) -> CommunityMembership:
    membership, created = CommunityMembership.objects.get_or_create(
        community=community,
        user=user,
        defaults={"active": True},
    )
    if not created and not membership.active:
        membership.active = True
        membership.left_at = None
        membership.save(update_fields=["active", "left_at"])
    return membership


def _new_unique_slug(name: str) -> str:
    base = slugify(name)[:70] or "community"
    slug = base
    suffix = 2
    while Community.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _chat_payload(message: ChatMessage, include_group: bool = False) -> dict:
    profile = getattr(message.user, "profile", None)
    avatar_url = _avatar_url_from_profile(profile)
    payload = {
        "id": message.id,
        "username": message.user.username,
        "display_name": _display_name_for_user(message.user),
        "avatar_url": avatar_url,
        "message": message.message,
        "created_at": message.created_at.isoformat(),
    }
    if include_group:
        payload["group_name"] = message.community.name
        payload["group_slug"] = message.community.slug
    return payload


def _chat_groups_for_memberships(
    memberships: list[CommunityMembership],
) -> list[dict]:
    groups = [{
        "slug": "global",
        "name": "Global",
        "messages_url": "/api/chat/messages/",
        "send_url": "/api/chat/send/",
    }]
    for membership in memberships:
        slug = membership.community.slug
        groups.append({
            "slug": slug,
            "name": membership.community.name,
            "messages_url": f"/c/{slug}/api/chat/messages/",
            "send_url": f"/c/{slug}/api/chat/send/",
        })
    return groups


def _pagination_arg(request: HttpRequest, key: str, default: int) -> int:
    raw = request.GET.get(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _community_member_rows(community: Community) -> list[dict]:
    memberships = list(
        CommunityMembership.objects.filter(
            community=community,
            active=True,
        )
        .select_related("user")
        .order_by("joined_at")
    )

    pixel_rows = (
        UserAction.objects.filter(
            community=community,
            accepted=True,
            user_key__startswith="user:",
        )
        .values("user_key")
        .annotate(pixel_count=Count("id"))
    )
    counts_by_id: dict[int, int] = {}
    for row in pixel_rows:
        parts = str(row["user_key"]).split(":", 1)
        if len(parts) != 2:
            continue
        try:
            user_id = int(parts[1])
        except ValueError:
            continue
        counts_by_id[user_id] = int(row["pixel_count"])

    rows = []
    for membership in memberships:
        profile = getattr(membership.user, "profile", None)
        rows.append({
            "user": membership.user,
            "avatar_url": _avatar_url_from_profile(profile),
            "joined_at": membership.joined_at,
            "pixel_count": counts_by_id.get(membership.user_id, 0),
        })
    return rows


def _snapshot_for_community(community: Community) -> JsonResponse:
    pixels = list(Pixel.objects.filter(community=community).values("x", "y", "color"))
    max_coord = -1
    for pixel in pixels:
        max_coord = max(max_coord, int(pixel["x"]), int(pixel["y"]))
    metrics = _grid_metrics_for_state(len(pixels), max_coord=max_coord)
    response = JsonResponse({
        "pixels": pixels,
        "grid_size": metrics["grid_size"],
        "filled_pixels": metrics["filled_pixels"],
        "fill_ratio": metrics["fill_ratio"],
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    community = _global_community(request)
    if community is None:
        return render(
            request,
            "pixelwar/community_lobby.html",
            _base_nav_context(request, active_tab="canvas", community=None),
        )
    current_user_key = f"user:{request.user.pk}" if request.user.is_authenticated else ""
    memberships = _non_global_memberships_for_user(request.user)
    chat_groups = _chat_groups_for_memberships(memberships)
    metrics = _current_grid_metrics(community)
    context = {
        **_base_nav_context(request, active_tab="canvas", community=None),
        "grid_size": metrics["grid_size"],
        "filled_pixels": metrics["filled_pixels"],
        "fill_ratio": metrics["fill_ratio"],
        "current_user_key": current_user_key,
        "pixel_snapshot_url": "/api/pixels/",
        "my_pixels_url": "/api/pixels/mine/",
        "pixel_update_url": "/api/pixels/update/",
        "chat_messages_url": "/api/chat/messages/",
        "chat_all_messages_url": "/api/chat/messages/grouped/",
        "chat_send_url": "/api/chat/send/",
        "pixels_ws_url": "/ws/c/global/pixels/",
        "chat_ws_url": "/ws/c/global/chat/",
        "memberships": memberships,
        "chat_grouped": bool(memberships),
        "chat_groups": chat_groups,
        "chat_default_group_slug": "global",
        "chat_can_send": _user_can_use_chat(request.user),
    }
    return render(request, "pixelwar/index.html", context)


@require_GET
def communities_lobby(request: HttpRequest) -> HttpResponse:
    memberships = _non_global_memberships_for_user(request.user)
    public_communities = _public_communities_for_lobby(request.user)
    can_create_community = False
    owned_communities_count = 0
    if request.user.is_authenticated:
        can_create_community = _user_can_use_chat(request.user)
        owned_communities_count = _owned_communities_count_for_user(request.user)

        owned_public_community_ids = [
            membership.community_id
            for membership in memberships
            if (
                membership.community.owner_id == request.user.id
                and membership.community.is_public
            )
        ]
        pending_counts: dict[int, int] = {}
        if owned_public_community_ids:
            pending_counts = dict(
                CommunityJoinRequest.objects.filter(
                    community_id__in=owned_public_community_ids,
                    status=CommunityJoinRequest.STATUS_PENDING,
                )
                .values("community_id")
                .annotate(total=Count("id"))
                .values_list("community_id", "total")
            )

        for membership in memberships:
            membership.pending_requests_count = int(
                pending_counts.get(membership.community_id, 0)
            )

    can_open_create_community = (
        request.user.is_authenticated
        and can_create_community
        and owned_communities_count < MAX_OWNED_COMMUNITIES
    )

    context = {
        **_base_nav_context(request, active_tab="communities", community=None),
        "memberships": memberships,
        "public_communities": public_communities,
        "can_create_community": can_create_community,
        "can_open_create_community": can_open_create_community,
        "owned_communities_count": owned_communities_count,
        "max_owned_communities": MAX_OWNED_COMMUNITIES,
    }
    return render(request, "pixelwar/community_lobby.html", context)


@require_GET
def global_leaders(request: HttpRequest) -> HttpResponse:
    is_htmx = request.headers.get("HX-Request") == "true"
    htmx_target = request.headers.get("HX-Target")
    community = _global_community(request)
    if community is None:
        return redirect("communities")
    context = {
        "top_players": _top_users_by_pixels(community),
        "canvas_url": reverse("index"),
    }
    if is_htmx and htmx_target == "leaders-content":
        return render(request, "pixelwar/leaders_partial.html", context)
    context.update({
        **_base_nav_context(request, active_tab="leaders", community=None),
        "memberships": _non_global_memberships_for_user(request.user),
    })
    return render(request, "pixelwar/leaders.html", context)


@require_GET
def global_guide(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pixelwar/guide.html",
        _base_nav_context(request, active_tab="guide", community=None),
    )


@require_GET
def privacy_policy(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pixelwar/privacy.html",
        _base_nav_context(request, active_tab=None, community=None),
    )


@require_GET
def terms_of_service(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "pixelwar/terms.html",
        _base_nav_context(request, active_tab=None, community=None),
    )


@login_required
def create_community(request: HttpRequest) -> HttpResponse:
    owned_communities_count = _owned_communities_count_for_user(request.user)

    if request.method == "GET":
        context = {
            **_base_nav_context(request, active_tab="communities", community=None),
            "can_create_community": _user_can_use_chat(request.user),
            "owned_communities_count": owned_communities_count,
            "max_owned_communities": MAX_OWNED_COMMUNITIES,
        }
        return render(request, "pixelwar/create_community.html", context)

    if not _user_can_use_chat(request.user):
        messages.error(
            request,
            "Confirm your email before creating your own community.",
            extra_tags="community",
        )
        return redirect("create-community")

    if owned_communities_count >= MAX_OWNED_COMMUNITIES:
        messages.error(
            request,
            "You can create up to 5 communities.",
            extra_tags="community",
        )
        return redirect("create-community")

    name = str(request.POST.get("name", "")).strip()
    if not name:
        messages.error(
            request,
            "Community name is required.",
            extra_tags="community",
        )
        return redirect("create-community")
    if len(name) < 3:
        messages.error(
            request,
            "Community name must be at least 3 characters.",
            extra_tags="community",
        )
        return redirect("create-community")
    description = str(request.POST.get("description", "")).strip()
    description = description[:280]
    visibility = str(request.POST.get("visibility", "private")).strip().lower()
    is_public = visibility == "public"
    max_members_raw = str(request.POST.get("max_members", "50")).strip()
    allowed_max_members = {5, 10, 20, 30, 50}
    try:
        max_members = int(max_members_raw)
    except ValueError:
        max_members = 50
    if max_members not in allowed_max_members:
        max_members = 50
    image = request.FILES.get("image")

    slug = _new_unique_slug(name)
    community = Community.objects.create(
        owner=request.user,
        name=name[:64],
        description=description,
        slug=slug,
        image=image,
        is_public=is_public,
        max_members=max_members if is_public else 50,
    )
    _join_community(request.user, community)
    return redirect("community-detail", slug=community.slug)


@require_POST
@login_required
def request_join_public_community(request: HttpRequest, slug: str) -> HttpResponse:
    community = Community.objects.filter(slug=slug, is_public=True).first()
    is_htmx = request.headers.get("HX-Request") == "true"

    if community is None:
        msg = "Public community was not found."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("communities")

    if community.owner_id == request.user.id:
        msg = "You already own this community."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-slate-100 px-3 py-1.5 text-xs '
                f'font-semibold text-slate-700">{msg}</span>'
            )
        messages.info(request, msg, extra_tags="community")
        return redirect("communities")

    is_member = CommunityMembership.objects.filter(
        community=community,
        user=request.user,
        active=True,
    ).exists()
    if is_member:
        msg = "You are already a member of this community."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-emerald-100 px-3 py-1.5 text-xs '
                f'font-semibold text-emerald-700">{msg}</span>'
            )
        messages.info(request, msg, extra_tags="community")
        return redirect("communities")

    if _is_public_community_full(community):
        msg = "This community is full."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-rose-100 px-3 py-1.5 text-xs '
                f'font-semibold text-rose-700">{msg}</span>'
            )
        messages.error(request, msg, extra_tags="community")
        return redirect("communities")

    join_request, created = CommunityJoinRequest.objects.get_or_create(
        community=community,
        user=request.user,
        defaults={"status": CommunityJoinRequest.STATUS_PENDING},
    )

    if created:
        notification_signals.community_join_requested.send_robust(
            sender=type(community),
            requester=request.user,
            community=community,
        )
        msg = "Join request sent."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-emerald-100 px-3 py-1.5 text-xs '
                f'font-semibold text-emerald-700">{msg}</span>'
            )
        messages.success(request, msg, extra_tags="community")
        return redirect("communities")

    if join_request.status == CommunityJoinRequest.STATUS_PENDING:
        msg = "You already have a pending join request."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-yellow-100 px-3 py-1.5 text-xs '
                f'font-semibold text-yellow-700">{msg}</span>'
            )
        messages.info(request, msg, extra_tags="community")
        return redirect("communities")

    if join_request.status == CommunityJoinRequest.STATUS_APPROVED:
        join_request.status = CommunityJoinRequest.STATUS_PENDING
        join_request.reviewed_at = None
        join_request.save(update_fields=["status", "reviewed_at"])
        notification_signals.community_join_requested.send_robust(
            sender=type(community),
            requester=request.user,
            community=community,
        )
        msg = "Join request sent."
        if is_htmx:
            return HttpResponse(
                f'<span class="rounded-lg bg-emerald-100 px-3 py-1.5 text-xs '
                f'font-semibold text-emerald-700">{msg}</span>'
            )
        messages.success(request, msg, extra_tags="community")
        return redirect("communities")

    join_request.status = CommunityJoinRequest.STATUS_PENDING
    join_request.reviewed_at = None
    join_request.save(update_fields=["status", "reviewed_at"])
    notification_signals.community_join_requested.send_robust(
        sender=type(community),
        requester=request.user,
        community=community,
    )
    msg = "Join request re-sent."
    if is_htmx:
        return HttpResponse(
            f'<span class="rounded-lg bg-emerald-100 px-3 py-1.5 text-xs '
            f'font-semibold text-emerald-700">{msg}</span>'
        )
    messages.success(request, msg, extra_tags="community")
    return redirect("communities")


@require_POST
@login_required
def approve_join_request(
    request: HttpRequest,
    slug: str,
    request_id: int,
) -> HttpResponse:
    is_htmx = request.headers.get("HX-Request") == "true"
    community = Community.objects.filter(slug=slug).first()
    if community is None:
        msg = "Community was not found."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("communities")
    if community.owner_id != request.user.id:
        msg = "Only owner can review join requests."
        if is_htmx:
            return HttpResponse(msg, status=403)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)
    if not community.is_public:
        msg = "Join requests exist only for public communities."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)

    join_request = CommunityJoinRequest.objects.filter(
        id=request_id,
        community=community,
        status=CommunityJoinRequest.STATUS_PENDING,
    ).select_related("user").first()
    if join_request is None:
        msg = "Join request was not found."
        if is_htmx:
            return HttpResponse(msg, status=404)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)
    if _is_public_community_full(community):
        msg = "Community is full. Cannot approve more members."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)

    _join_community(join_request.user, community)
    join_request.status = CommunityJoinRequest.STATUS_APPROVED
    join_request.reviewed_at = datetime.now(timezone.utc)
    join_request.save(update_fields=["status", "reviewed_at"])
    notification_signals.community_join_reviewed.send_robust(
        sender=type(community),
        requester=join_request.user,
        community=community,
        approved=True,
    )
    if is_htmx:
        return HttpResponse("")
    messages.success(
        request,
        f"Approved {join_request.user.username}.",
        extra_tags="community",
    )
    return redirect("community-detail", slug=slug)


@require_POST
@login_required
def decline_join_request(
    request: HttpRequest,
    slug: str,
    request_id: int,
) -> HttpResponse:
    is_htmx = request.headers.get("HX-Request") == "true"
    community = Community.objects.filter(slug=slug).first()
    if community is None:
        msg = "Community was not found."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("communities")
    if community.owner_id != request.user.id:
        msg = "Only owner can review join requests."
        if is_htmx:
            return HttpResponse(msg, status=403)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)
    if not community.is_public:
        msg = "Join requests exist only for public communities."
        if is_htmx:
            return HttpResponse(msg, status=400)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)

    join_request = CommunityJoinRequest.objects.filter(
        id=request_id,
        community=community,
        status=CommunityJoinRequest.STATUS_PENDING,
    ).select_related("user").first()
    if join_request is None:
        msg = "Join request was not found."
        if is_htmx:
            return HttpResponse(msg, status=404)
        messages.error(request, msg, extra_tags="community")
        return redirect("community-detail", slug=slug)
    join_request.status = CommunityJoinRequest.STATUS_DECLINED
    join_request.reviewed_at = datetime.now(timezone.utc)
    join_request.save(update_fields=["status", "reviewed_at"])
    notification_signals.community_join_reviewed.send_robust(
        sender=type(community),
        requester=join_request.user,
        community=community,
        approved=False,
    )
    if is_htmx:
        return HttpResponse("")
    messages.success(
        request,
        f"Declined {join_request.user.username}.",
        extra_tags="community",
    )
    return redirect("community-detail", slug=slug)


@require_GET
def invitation_view(request: HttpRequest, token: str) -> HttpResponse:
    community = get_object_or_404(Community, invite_token=token)
    if community.slug == "global":
        return redirect("index")
    already_member = False
    if request.user.is_authenticated:
        already_member = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
            active=True,
        ).exists()
    context = {
        **_base_nav_context(request, active_tab="communities", community=None),
        "invite_community": community,
        "already_member": already_member,
    }
    return render(request, "pixelwar/invitation.html", context)


@require_POST
def invitation_accept(request: HttpRequest, token: str) -> HttpResponse:
    community = get_object_or_404(Community, invite_token=token)
    if community.slug == "global":
        return redirect("index")
    if not request.user.is_authenticated:
        request.session["pending_invite_token"] = str(token)
        messages.info(
            request,
            "Please login or register first, then click invitation link again.",
            extra_tags="auth",
        )
        return redirect("invitation", token=community.invite_token)
    _join_community(request.user, community)
    return redirect("community-canvas", slug=community.slug)


@require_POST
@login_required
def leave_community(request: HttpRequest, slug: str) -> HttpResponse:
    if slug == "global":
        return redirect("index")
    membership = CommunityMembership.objects.filter(
        community__slug=slug,
        user=request.user,
        active=True,
    ).first()
    if membership is None:
        return redirect("communities")
    if membership.community.owner_id == request.user.id:
        messages.error(
            request,
            "You cannot leave your own community. Delete it instead.",
            extra_tags="community",
        )
        return redirect("communities")

    membership.active = False
    membership.left_at = datetime.now(timezone.utc)
    membership.save(update_fields=["active", "left_at"])
    return redirect("communities")


@require_POST
@login_required
def delete_community(request: HttpRequest, slug: str) -> HttpResponse:
    community = Community.objects.filter(slug=slug).first()
    if community is None:
        messages.error(
            request,
            "Community was not found.",
            extra_tags="community",
        )
        return redirect("communities")

    if community.owner_id != request.user.id:
        messages.error(
            request,
            "Only the community owner can delete it.",
            extra_tags="community",
        )
        return redirect("communities")

    if community.slug == "global":
        messages.error(
            request,
            "Global community cannot be deleted.",
            extra_tags="community",
        )
        return redirect("communities")

    community_name = community.name
    community.delete()
    messages.success(
        request,
        f'Community "{community_name}" was deleted.',
        extra_tags="community",
    )
    return redirect("communities")


@require_POST
@login_required
def remove_community_member(
    request: HttpRequest,
    slug: str,
    user_id: int,
) -> HttpResponse:
    community = Community.objects.filter(slug=slug).first()
    if community is None:
        messages.error(
            request,
            "Community was not found.",
            extra_tags="community",
        )
        return redirect("communities")

    if community.owner_id != request.user.id:
        messages.error(
            request,
            "Only the community owner can remove members.",
            extra_tags="community",
        )
        return redirect("community-detail", slug=slug)

    if user_id == request.user.id:
        messages.error(
            request,
            "Owner cannot remove themselves.",
            extra_tags="community",
        )
        return redirect("community-detail", slug=slug)

    membership = CommunityMembership.objects.filter(
        community=community,
        user_id=user_id,
        active=True,
    ).select_related("user").first()
    if membership is None:
        messages.error(
            request,
            "Member was not found.",
            extra_tags="community",
        )
        return redirect("community-detail", slug=slug)

    membership.active = False
    membership.left_at = datetime.now(timezone.utc)
    membership.save(update_fields=["active", "left_at"])
    messages.success(
        request,
        f"{membership.user.username} was removed from the community.",
        extra_tags="community",
    )
    return redirect("community-detail", slug=slug)


@require_GET
@login_required
def community_canvas(request: HttpRequest, slug: str) -> HttpResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return redirect("communities")
    metrics = _current_grid_metrics(community)
    memberships = _non_global_memberships_for_user(request.user)
    chat_groups = _chat_groups_for_memberships(memberships)
    context = {
        **_base_nav_context(request, active_tab="communities",
                            community=community),
        "grid_size": metrics["grid_size"],
        "filled_pixels": metrics["filled_pixels"],
        "fill_ratio": metrics["fill_ratio"],
        "current_user_key": f"user:{request.user.pk}",
        "pixel_snapshot_url": f"/c/{community.slug}/api/pixels/",
        "my_pixels_url": f"/c/{community.slug}/api/pixels/mine/",
        "pixel_update_url": f"/c/{community.slug}/api/pixels/update/",
        "chat_messages_url": f"/c/{community.slug}/api/chat/messages/",
        "chat_all_messages_url": "/api/chat/messages/grouped/",
        "chat_send_url": f"/c/{community.slug}/api/chat/send/",
        "pixels_ws_url": f"/ws/c/{community.slug}/pixels/",
        "chat_ws_url": f"/ws/c/{community.slug}/chat/",
        "memberships": memberships,
        "chat_grouped": bool(memberships),
        "chat_groups": chat_groups,
        "chat_default_group_slug": "global",
        "chat_can_send": _user_can_use_chat(request.user),
    }
    return render(request, "pixelwar/index.html", context)


@require_GET
@login_required
def community_leaders(request: HttpRequest, slug: str) -> HttpResponse:
    is_htmx = request.headers.get("HX-Request") == "true"
    htmx_target = request.headers.get("HX-Target")
    community = _community_for_user(request.user, slug)
    if community is None:
        return redirect("communities")
    context = {
        "top_players": _top_users_by_pixels(community),
        "canvas_url": reverse("community-canvas", kwargs={"slug": slug}),
    }
    if is_htmx and htmx_target == "leaders-content":
        return render(request, "pixelwar/leaders_partial.html", context)
    context.update({
        **_base_nav_context(request, active_tab="leaders",
                            community=community),
        "memberships": _non_global_memberships_for_user(request.user),
    })
    return render(request, "pixelwar/leaders.html", context)


@require_GET
@login_required
def community_guide(request: HttpRequest, slug: str) -> HttpResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return redirect("communities")
    return render(
        request,
        "pixelwar/guide.html",
        _base_nav_context(request, active_tab="communities",
                          community=community),
    )


@require_GET
def community_detail(request: HttpRequest, slug: str) -> HttpResponse:
    community = Community.objects.filter(slug=slug).select_related("owner").first()
    if community is None:
        messages.error(
            request,
            "Community was not found.",
            extra_tags="community",
        )
        return redirect("communities")

    is_member = False
    if request.user.is_authenticated:
        is_member = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
            active=True,
        ).exists()

    is_owner = (
        request.user.is_authenticated
        and community.owner_id == request.user.id
    )
    can_view_full_details = is_owner or is_member
    can_view_general_details = can_view_full_details or community.is_public
    if not can_view_general_details:
        messages.error(
            request,
            "You cannot view details of this community.",
            extra_tags="community",
        )
        return redirect("communities")

    sort_key = str(request.GET.get("sort", "joined")).strip().lower()
    if sort_key not in {"joined", "pixels"}:
        sort_key = "joined"

    sort_dir = str(request.GET.get("dir", "asc")).strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    member_rows: list[dict] = []
    if can_view_full_details:
        member_rows = _community_member_rows(community)
        reverse = sort_dir == "desc"
        if sort_key == "pixels":
            member_rows.sort(
                key=lambda item: (item["pixel_count"], item["joined_at"]),
                reverse=reverse,
            )
        else:
            member_rows.sort(
                key=lambda item: (item["joined_at"], item["pixel_count"]),
                reverse=reverse,
            )

    member_count = _community_active_member_count(community)

    pixels_qs = list(
        Pixel.objects.filter(community=community).values("x", "y", "color")
    )
    max_coord = -1
    for px in pixels_qs:
        max_coord = max(max_coord, int(px["x"]), int(px["y"]))
    metrics = _grid_metrics_for_state(len(pixels_qs), max_coord=max_coord)

    pending_join_request_rows: list[dict] = []
    if community.is_public and is_owner:
        pending_requests = list(
            CommunityJoinRequest.objects.filter(
                community=community,
                status=CommunityJoinRequest.STATUS_PENDING,
            )
            .select_related("user", "user__profile")
            .order_by("created_at")
        )

        requester_ids = [row.user_id for row in pending_requests]
        community_counts_by_user: dict[int, int] = {}
        global_pixels_by_user: dict[int, int] = {}

        if requester_ids:
            community_counts_by_user = dict(
                CommunityMembership.objects.filter(
                    user_id__in=requester_ids,
                    active=True,
                )
                .exclude(community__slug__iexact="global")
                .values("user_id")
                .annotate(total=Count("id"))
                .values_list("user_id", "total")
            )

            global_community_id = (
                Community.objects.filter(slug__iexact="global")
                .values_list("id", flat=True)
                .first()
            )
            if global_community_id is not None:
                user_keys = [f"user:{user_id}" for user_id in requester_ids]
                global_rows = (
                    UserAction.objects.filter(
                        community_id=global_community_id,
                        accepted=True,
                        user_key__in=user_keys,
                    )
                    .values("user_key")
                    .annotate(total=Count("id"))
                )
                for stat_row in global_rows:
                    raw_key = str(stat_row.get("user_key", ""))
                    parts = raw_key.split(":", 1)
                    if len(parts) != 2:
                        continue
                    try:
                        stat_user_id = int(parts[1])
                    except ValueError:
                        continue
                    global_pixels_by_user[stat_user_id] = int(
                        stat_row["total"]
                    )

        for join_req in pending_requests:
            profile = getattr(join_req.user, "profile", None)
            avatar_url = _avatar_url_from_profile(profile)
            pending_join_request_rows.append({
                "request": join_req,
                "avatar_url": avatar_url,
                "email": join_req.user.email,
                "global_pixel_count": global_pixels_by_user.get(
                    join_req.user_id,
                    0,
                ),
                "joined_communities_count": community_counts_by_user.get(
                    join_req.user_id,
                    0,
                ),
            })

    context = {
        **_base_nav_context(request, active_tab="communities", community=community),
        "community": community,
        "memberships": _non_global_memberships_for_user(request.user),
        "is_owner": is_owner,
        "is_member": is_member,
        "can_view_full_details": can_view_full_details,
        "member_rows": member_rows,
        "member_count": member_count,
        "pixel_count": len(pixels_qs),
        "is_public_full": (
            community.is_public
            and member_count >= int(community.max_members)
        ),
        "pending_join_requests": pending_join_request_rows,
        "sort": sort_key,
        "dir": sort_dir,
        "canvas_grid_size": metrics["grid_size"],
        "canvas_pixels_json": json.dumps(pixels_qs),
    }
    return render(request, "pixelwar/community_detail.html", context)


@require_GET
def pixel_snapshot(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    return _snapshot_for_community(community)


@require_GET
@login_required
def my_pixels(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    target_user_key = f"user:{request.user.pk}"
    max_coords = Pixel.objects.filter(community=community).count()
    seen: set[tuple[int, int]] = set()
    owned: list[list[int]] = []
    actions = (
        UserAction.objects.filter(community=community, accepted=True)
        .order_by("-created_at", "-id")
        .values("x", "y", "user_key")
    )
    for action in actions.iterator(chunk_size=2000):
        coord = (int(action["x"]), int(action["y"]))
        if coord in seen:
            continue
        seen.add(coord)
        if action["user_key"] == target_user_key:
            owned.append([coord[0], coord[1]])
        if len(seen) >= max_coords:
            break
    return JsonResponse({"pixels": owned, "count": len(owned)})


@require_GET
def chat_messages(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    limit = min(max(_pagination_arg(request, "limit", 20), 1), 100)
    offset = max(_pagination_arg(request, "offset", 0), 0)
    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community=community)
        .select_related("user")
        .order_by("-created_at", "-id")[offset:offset + limit]
    )
    payload = [_chat_payload(msg) for msg in reversed(list(recent))]
    return JsonResponse({
        "messages": payload,
        "limit": limit,
        "offset": offset,
        "has_more": len(payload) == limit,
    })


@require_GET
def grouped_chat_messages(request: HttpRequest) -> JsonResponse:
    global_community = _global_community(request)
    if global_community is None:
        return JsonResponse({"status": "unavailable"}, status=503)

    community_ids = [global_community.id]
    if request.user.is_authenticated:
        memberships = _non_global_memberships_for_user(request.user)
        community_ids.extend(m.community_id for m in memberships)

    limit = min(max(_pagination_arg(request, "limit", 60), 1), 200)
    offset = max(_pagination_arg(request, "offset", 0), 0)
    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community_id__in=community_ids)
        .select_related("user", "community")
        .order_by("-created_at", "-id")[offset:offset + limit]
    )
    payload = [_chat_payload(msg, include_group=True)
               for msg in reversed(list(recent))]
    return JsonResponse({
        "messages": payload,
        "limit": limit,
        "offset": offset,
        "has_more": len(payload) == limit,
    })


@require_POST
def chat_send(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    if not request.user.is_authenticated:
        return JsonResponse({"status": "unauthorized"}, status=401)
    if not _user_can_use_chat(request.user):
        return JsonResponse({"status": "email_not_activated"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON payload")
    text = str(payload.get("message", "")).strip()
    if not text:
        return HttpResponseBadRequest("Message is required")
    if len(text) > 500:
        return HttpResponseBadRequest("Message too long")
    cooldown_key = f"chatcooldown:global:{request.user.id}"
    if not cache.add(cooldown_key, "1", timeout=5):
        redis_conn = get_redis_connection("default")
        ttl = redis_conn.ttl(cooldown_key)
        if ttl is None or ttl < 0:
            ttl = 2
        return JsonResponse({"status": "cooldown", "retry_after": ttl}, status=429)
    profile = getattr(request.user, "profile", None)
    avatar_url = _avatar_url_from_profile(profile)
    display_name = _display_name_for_user(request.user)
    now = datetime.now(timezone.utc)
    temp_id = str(uuid.uuid4())
    ws_payload = {
        "username": request.user.username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "message": text,
        "created_at": now.isoformat(),
        "temp_id": temp_id,
    }
    try:
        _channel_group_send(
            f"chat_messages_{community.slug}",
            {"type": "chat_message", "payload": ws_payload},
        )
    except Exception:
        pass
    try:
        enqueue_chat_message({
            "community_slug": community.slug,
            "user_id": request.user.id,
            "username": request.user.username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "message": text,
            "created_at": now.isoformat(),
            "temp_id": temp_id,
        })
    except (NoBrokersAvailable, KafkaError):
        try:
            _channel_group_send(
                f"chat_messages_{community.slug}",
                {
                    "type": "chat_revert",
                    "payload": {"type": "chat_revert", "temp_id": temp_id},
                },
            )
        except Exception:
            pass
        cache.delete(cooldown_key)
        return JsonResponse({"status": "service_unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_POST
def update_pixel(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    return _update_pixel_for_community(request, community, "global")


def _update_pixel_for_community(
    request: HttpRequest,
    community: Community,
    cooldown_scope: str,
) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON payload")
    metrics_now = _current_grid_metrics(community)
    grid_size = int(metrics_now["grid_size"])
    x = payload.get("x")
    y = payload.get("y")
    color = payload.get("color")
    if not isinstance(x, int) or not isinstance(y, int):
        return HttpResponseBadRequest("Coordinates must be integers")
    if x < 0 or y < 0 or x >= grid_size or y >= grid_size:
        return HttpResponseBadRequest("Coordinates out of bounds")
    if not isinstance(color, str) or not HEX_COLOR_RE.match(color):
        return HttpResponseBadRequest("Color must be hex like #12ABEF")

    user_key = _user_key(request)
    ip_address = _client_ip(request)
    cooldown_key = f"cooldown:{cooldown_scope}:{user_key}"
    cooldown_seconds = settings.COOLDOWN_SECONDS
    now = datetime.now(timezone.utc)

    if not cache.add(cooldown_key, now.isoformat(), timeout=cooldown_seconds):
        redis_conn = get_redis_connection("default")
        ttl = redis_conn.ttl(cooldown_key)
        if ttl is None or ttl < 0:
            ttl = cooldown_seconds
        UserAction.objects.create(
            community=community,
            user_key=user_key,
            ip_address=ip_address,
            x=x,
            y=y,
            color=color,
            accepted=False,
            rejection_reason="cooldown",
        )
        return JsonResponse({"status": "cooldown", "retry_after": ttl}, status=429)

    action = UserAction.objects.create(
        community=community,
        user_key=user_key,
        ip_address=ip_address,
        x=x,
        y=y,
        color=color,
        accepted=True,
    )
    # Look up the pre-existing pixel colour (used for metrics and revert).
    old_pixel = Pixel.objects.filter(
        community=community, x=x, y=y
    ).values_list("color", flat=True).first()
    old_color: str = old_pixel if old_pixel else "#ffffff"
    pixel_exists = old_pixel is not None
    projected_count = int(metrics_now["filled_pixels"]) + (0 if pixel_exists else 1)
    projected_metrics = _grid_metrics_for_state(
        projected_count, max_coord=max(x, y)
    )
    # Broadcast immediately so all clients see the pixel without waiting for
    # the Kafka → DB round-trip.
    try:
        _channel_group_send(
            f"pixel_updates_{community.slug}",
            {
                "type": "pixel_update",
                "payload": {"x": x, "y": y, "color": color, "user_key": user_key},
            },
        )
    except Exception:
        pass  # Channel layer unavailable – clients will see update on next snapshot.
    try:
        enqueue_pixel_update({
            "community_slug": community.slug,
            "x": x,
            "y": y,
            "color": color,
            "user_key": user_key,
            "at": now.isoformat(),
        })
    except (NoBrokersAvailable, KafkaError):
        # Kafka is down – revert the optimistic WS update for all clients.
        try:
            _channel_group_send(
                f"pixel_updates_{community.slug}",
                {
                    "type": "pixel_revert",
                    "payload": {
                        "type": "pixel_revert",
                        "x": x,
                        "y": y,
                        "color": old_color,
                    },
                },
            )
        except Exception:
            pass
        cache.delete(cooldown_key)
        action.accepted = False
        action.rejection_reason = "kafka_unavailable"
        action.save(update_fields=["accepted", "rejection_reason"])
        return JsonResponse({"status": "service_unavailable"}, status=503)

    return JsonResponse({
        "status": "ok",
        "cooldown_seconds": cooldown_seconds,
        "grid_size": projected_metrics["grid_size"],
        "filled_pixels": projected_metrics["filled_pixels"],
        "fill_ratio": projected_metrics["fill_ratio"],
    })


@require_GET
@login_required
def community_pixel_snapshot(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    return _snapshot_for_community(community)


@require_GET
@login_required
def community_my_pixels(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    target_user_key = f"user:{request.user.pk}"
    max_coords = Pixel.objects.filter(community=community).count()
    seen: set[tuple[int, int]] = set()
    owned: list[list[int]] = []
    actions = (
        UserAction.objects.filter(community=community, accepted=True)
        .order_by("-created_at", "-id")
        .values("x", "y", "user_key")
    )
    for action in actions.iterator(chunk_size=2000):
        coord = (int(action["x"]), int(action["y"]))
        if coord in seen:
            continue
        seen.add(coord)
        if action["user_key"] == target_user_key:
            owned.append([coord[0], coord[1]])
        if len(seen) >= max_coords:
            break
    return JsonResponse({"pixels": owned, "count": len(owned)})


@require_GET
@login_required
def community_chat_messages(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    limit = min(max(_pagination_arg(request, "limit", 20), 1), 100)
    offset = max(_pagination_arg(request, "offset", 0), 0)
    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community=community)
        .select_related("user")
        .order_by("-created_at", "-id")[offset:offset + limit]
    )
    payload = [_chat_payload(msg) for msg in reversed(list(recent))]
    return JsonResponse({
        "messages": payload,
        "limit": limit,
        "offset": offset,
        "has_more": len(payload) == limit,
    })


@require_POST
@login_required
def community_chat_send(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    if not _user_can_use_chat(request.user):
        return JsonResponse({"status": "email_not_activated"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON payload")
    text = str(payload.get("message", "")).strip()
    if not text:
        return HttpResponseBadRequest("Message is required")
    if len(text) > 500:
        return HttpResponseBadRequest("Message too long")
    cooldown_key = f"chatcooldown:{slug}:{request.user.id}"
    if not cache.add(cooldown_key, "1", timeout=20):
        redis_conn = get_redis_connection("default")
        ttl = redis_conn.ttl(cooldown_key)
        if ttl is None or ttl < 0:
            ttl = 2
        return JsonResponse({"status": "cooldown", "retry_after": ttl}, status=429)
    profile = getattr(request.user, "profile", None)
    avatar_url = _avatar_url_from_profile(profile)
    display_name = _display_name_for_user(request.user)
    now = datetime.now(timezone.utc)
    temp_id = str(uuid.uuid4())
    ws_payload = {
        "username": request.user.username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "message": text,
        "created_at": now.isoformat(),
        "temp_id": temp_id,
    }
    try:
        _channel_group_send(
            f"chat_messages_{community.slug}",
            {"type": "chat_message", "payload": ws_payload},
        )
    except Exception:
        pass
    try:
        enqueue_chat_message({
            "community_slug": community.slug,
            "user_id": request.user.id,
            "username": request.user.username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "message": text,
            "created_at": now.isoformat(),
            "temp_id": temp_id,
        })
    except (NoBrokersAvailable, KafkaError):
        try:
            _channel_group_send(
                f"chat_messages_{community.slug}",
                {
                    "type": "chat_revert",
                    "payload": {"type": "chat_revert", "temp_id": temp_id},
                },
            )
        except Exception:
            pass
        cache.delete(cooldown_key)
        return JsonResponse({"status": "service_unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_POST
@login_required
def community_update_pixel(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    return _update_pixel_for_community(request, community, slug)
