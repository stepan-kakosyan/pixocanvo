from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from pixelwar.models import Community, CommunityMembership

from .forms import LoginForm, ProfileSettingsForm, RegisterForm


def _base_nav_context(request: HttpRequest) -> dict:
    return {
        "active_tab": None,
        "layout": (
            "partial"
            if request.headers.get("HX-Request") == "true"
            else "full"
        ),
    }


def _consume_pending_invite(request: HttpRequest, user) -> Community | None:
    token = request.session.pop("pending_invite_token", None)
    if not token:
        return None

    community = Community.objects.filter(invite_token=token).first()
    if community is None:
        return None

    membership, created = CommunityMembership.objects.get_or_create(
        community=community,
        user=user,
        defaults={"active": True},
    )
    if not created and not membership.active:
        membership.active = True
        membership.left_at = None
        membership.save(update_fields=["active", "left_at"])

    return community


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            invited_community = _consume_pending_invite(request, user)
            messages.success(request, "Welcome to Pixo Canvo!")
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                return redirect(
                    "community-canvas",
                    slug=invited_community.slug,
                )
            return redirect("index")
    else:
        form = RegisterForm()

    context = {"form": form}
    context.update(_base_nav_context(request))
    return render(request, "users/register.html", context)


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            invited_community = _consume_pending_invite(
                request,
                form.get_user(),
            )
            messages.success(request, "Logged in successfully.")
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                return redirect(
                    "community-canvas",
                    slug=invited_community.slug,
                )
            return redirect("index")
    else:
        form = LoginForm(request)

    context = {"form": form}
    context.update(_base_nav_context(request))
    return render(request, "users/login.html", context)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("index")


@login_required
def profile_settings_view(request: HttpRequest) -> HttpResponse:
    user = request.user
    previous_password_hash = user.password

    if request.method == "POST":
        form = ProfileSettingsForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            updated_user = form.save()
            if updated_user.password != previous_password_hash:
                update_session_auth_hash(request, updated_user)
            messages.success(request, "Profile updated successfully.")
            return redirect("profile-settings")
    else:
        form = ProfileSettingsForm(user=user)

    profile = getattr(user, "profile", None)
    avatar_url = ""
    if profile and profile.avatar:
        avatar_url = profile.avatar.url

    return render(
        request,
        "users/profile_settings.html",
        {
            "form": form,
            "avatar_url": avatar_url,
            "active_tab": None,
            "canvas_url": "/",
            "leaders_url": "/leaders/",
            "guide_url": "/guide/",
            "communities_url": "/communities/",
        },
    )
