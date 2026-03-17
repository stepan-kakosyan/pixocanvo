import json
import math
import re
from datetime import datetime, timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Max, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from django_redis import get_redis_connection
from kafka.errors import KafkaError, NoBrokersAvailable

from .kafka_producer import enqueue_chat_message, enqueue_pixel_update
from .models import ChatMessage, Community, CommunityMembership, Pixel, UserAction

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@require_GET
def switch_language(request: HttpRequest) -> HttpResponse:
    lang = str(request.GET.get("lang", "")).strip().lower()
    next_url = str(request.GET.get("next_url", "/")).strip()
    print("Requested language change to:", lang, "Next URL:", next_url)
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
    if profile and profile.avatar:
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
            "avatar_url": profile.avatar.url if profile and profile.avatar else "",
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
    avatar_url = profile.avatar.url if profile and profile.avatar else ""
    payload = {
        "id": message.id,
        "username": message.user.username,
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
        "send_url": "/api/chat/send/",
    }]
    for membership in memberships:
        slug = membership.community.slug
        groups.append({
            "slug": slug,
            "name": membership.community.name,
            "send_url": f"/c/{slug}/api/chat/send/",
        })
    return groups


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
            "avatar_url": profile.avatar.url if profile and profile.avatar else "",
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
    }
    return render(request, "pixelwar/index.html", context)


@require_GET
def communities_lobby(request: HttpRequest) -> HttpResponse:
    memberships = _non_global_memberships_for_user(request.user)
    owns_community = False
    if request.user.is_authenticated:
        owns_community = Community.objects.filter(
            owner=request.user).exclude(slug="global").exists()
    context = {
        **_base_nav_context(request, active_tab="communities", community=None),
        "memberships": memberships,
        "owns_community": owns_community,
    }
    return render(request, "pixelwar/community_lobby.html", context)


@require_GET
def global_leaders(request: HttpRequest) -> HttpResponse:
    community = _global_community(request)
    if community is None:
        return redirect("communities")
    context = {
        **_base_nav_context(request, active_tab="leaders", community=None),
        "top_players": _top_users_by_pixels(community),
        "memberships": _non_global_memberships_for_user(request.user),
    }
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


@require_POST
@login_required
def create_community(request: HttpRequest) -> HttpResponse:
    if Community.objects.filter(owner=request.user).exclude(slug="global").exists():
        messages.error(request, "You can create only one community.")
        return redirect("communities")

    name = str(request.POST.get("name", "")).strip()
    if not name:
        messages.error(request, "Community name is required.")
        return redirect("communities")
    if len(name) < 3:
        messages.error(request, "Community name must be at least 3 characters.")
        return redirect("communities")
    slug = _new_unique_slug(name)
    community = Community.objects.create(owner=request.user,
                                         name=name[:64], slug=slug)
    _join_community(request.user, community)
    return redirect("community-detail", slug=community.slug)


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
        messages.error(request, "Community was not found.")
        return redirect("communities")

    if community.owner_id != request.user.id:
        messages.error(request, "Only the community owner can delete it.")
        return redirect("communities")

    if community.slug == "global":
        messages.error(request, "Global community cannot be deleted.")
        return redirect("communities")

    community_name = community.name
    community.delete()
    messages.success(request, f'Community "{community_name}" was deleted.')
    return redirect("communities")


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
    }
    return render(request, "pixelwar/index.html", context)


@require_GET
@login_required
def community_leaders(request: HttpRequest, slug: str) -> HttpResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return redirect("communities")
    context = {
        **_base_nav_context(request, active_tab="leaders",
                            community=community),
        "top_players": _top_users_by_pixels(community),
        "memberships": _non_global_memberships_for_user(request.user),
    }
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
@login_required
def community_detail(request: HttpRequest, slug: str) -> HttpResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return redirect("communities")

    sort_key = str(request.GET.get("sort", "joined")).strip().lower()
    if sort_key not in {"joined", "pixels"}:
        sort_key = "joined"

    sort_dir = str(request.GET.get("dir", "asc")).strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

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

    pixels_qs = list(
        Pixel.objects.filter(community=community).values("x", "y", "color")
    )
    max_coord = -1
    for px in pixels_qs:
        max_coord = max(max_coord, int(px["x"]), int(px["y"]))
    metrics = _grid_metrics_for_state(len(pixels_qs), max_coord=max_coord)

    context = {
        **_base_nav_context(request, active_tab="communities", community=community),
        "community": community,
        "memberships": _non_global_memberships_for_user(request.user),
        "is_owner": community.owner_id == request.user.id,
        "member_rows": member_rows,
        "member_count": len(member_rows),
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
    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community=community)
        .select_related("user")
        .order_by("-created_at")[:100]
    )
    payload = [_chat_payload(msg) for msg in reversed(list(recent))]
    return JsonResponse({"messages": payload})


@require_GET
def grouped_chat_messages(request: HttpRequest) -> JsonResponse:
    global_community = _global_community(request)
    if global_community is None:
        return JsonResponse({"status": "unavailable"}, status=503)

    community_ids = [global_community.id]
    if request.user.is_authenticated:
        memberships = _non_global_memberships_for_user(request.user)
        community_ids.extend(m.community_id for m in memberships)

    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community_id__in=community_ids)
        .select_related("user", "community")
        .order_by("-created_at")[:120]
    )
    payload = [_chat_payload(msg, include_group=True)
               for msg in reversed(list(recent))]
    return JsonResponse({"messages": payload})


@require_POST
def chat_send(request: HttpRequest) -> JsonResponse:
    community = _global_community(request)
    if community is None:
        return JsonResponse({"status": "unavailable"}, status=503)
    if not request.user.is_authenticated:
        return JsonResponse({"status": "unauthorized"}, status=401)
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
    if not cache.add(cooldown_key, "1", timeout=20):
        redis_conn = get_redis_connection("default")
        ttl = redis_conn.ttl(cooldown_key)
        if ttl is None or ttl < 0:
            ttl = 2
        return JsonResponse({"status": "cooldown", "retry_after": ttl}, status=429)
    profile = getattr(request.user, "profile", None)
    avatar_url = profile.avatar.url if profile and profile.avatar else ""
    now = datetime.now(timezone.utc)
    try:
        enqueue_chat_message({
            "community_slug": community.slug,
            "user_id": request.user.id,
            "username": request.user.username,
            "avatar_url": avatar_url,
            "message": text,
            "created_at": now.isoformat(),
        })
    except (NoBrokersAvailable, KafkaError):
        cache.delete(cooldown_key)
        return JsonResponse({"status": "service_unavailable"}, status=503)
    return JsonResponse({"status": "queued"})


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
    try:
        pixel_exists = Pixel.objects.filter(community=community, x=x, y=y).exists()
        projected_count = int(metrics_now["filled_pixels"]) + (0 if pixel_exists else 1)
        projected_metrics = _grid_metrics_for_state(projected_count, max_coord=max(x, y))
        enqueue_pixel_update({
            "community_slug": community.slug,
            "x": x,
            "y": y,
            "color": color,
            "user_key": user_key,
            "at": now.isoformat(),
        })
    except (NoBrokersAvailable, KafkaError):
        cache.delete(cooldown_key)
        action.accepted = False
        action.rejection_reason = "kafka_unavailable"
        action.save(update_fields=["accepted", "rejection_reason"])
        return JsonResponse({"status": "service_unavailable"}, status=503)

    return JsonResponse({
        "status": "queued",
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
    recent: QuerySet[ChatMessage] = (
        ChatMessage.objects.filter(community=community)
        .select_related("user")
        .order_by("-created_at")[:100]
    )
    payload = [_chat_payload(msg) for msg in reversed(list(recent))]
    return JsonResponse({"messages": payload})


@require_POST
@login_required
def community_chat_send(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
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
    avatar_url = profile.avatar.url if profile and profile.avatar else ""
    now = datetime.now(timezone.utc)
    try:
        enqueue_chat_message({
            "community_slug": community.slug,
            "user_id": request.user.id,
            "username": request.user.username,
            "avatar_url": avatar_url,
            "message": text,
            "created_at": now.isoformat(),
        })
    except (NoBrokersAvailable, KafkaError):
        cache.delete(cooldown_key)
        return JsonResponse({"status": "service_unavailable"}, status=503)
    return JsonResponse({"status": "queued"})


@require_POST
@login_required
def community_update_pixel(request: HttpRequest, slug: str) -> JsonResponse:
    community = _community_for_user(request.user, slug)
    if community is None:
        return JsonResponse({"status": "forbidden"}, status=403)
    return _update_pixel_for_community(request, community, slug)
