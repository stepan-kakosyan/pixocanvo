from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from Notifications import signals as notification_signals
from pixelwar.models import Community, CommunityMembership

from .email_service import get_user_from_password_reset_token
from .email_service import send_account_activation_email
from .email_service import send_contact_us_email
from .email_service import send_password_reset_email
from .email_service import send_email_verification_email
from .forms import (
    AvatarUploadForm,
    ContactUsForm,
    ForgotPasswordForm,
    LoginForm,
    ProfileSettingsForm,
    RegisterForm,
)
from .models import ContactMessage, UserProfile
from django.db.models import Q


def _base_nav_context(request: HttpRequest) -> dict:
    return {
        "active_tab": None,
        "layout": (
            "partial"
            if request.headers.get("HX-Request") == "true"
            else "full"
        ),
    }


def contact_us_view(request: HttpRequest) -> HttpResponse:
    user_tickets = []
    if request.user.is_authenticated:
        ticket_filters = Q(user=request.user)
        user_email = (request.user.email or "").strip().lower()
        if user_email:
            ticket_filters |= Q(email__iexact=user_email)
        user_tickets = list(ContactMessage.objects.filter(ticket_filters).distinct())

    if request.method == "POST":
        form = ContactUsForm(
            request.POST,
            user=request.user,
        )
        if form.is_valid():
            contact_message = form.save()
            try:
                send_contact_us_email(request, contact_message)
            except Exception:
                messages.error(
                    request,
                    "Your message was received, but email delivery to support "
                    "failed. Please try again later.",
                    extra_tags="contact",
                )
                return redirect("contact-us")

            messages.success(
                request,
                "Your message has been sent successfully. Our team will review "
                "it soon.",
                extra_tags="contact",
            )
            return redirect("contact-us")
    else:
        form = ContactUsForm(user=request.user)

    context = {
        "form": form,
        "active_tab": None,
        "user_tickets": user_tickets,
    }
    context.update(_base_nav_context(request))
    return render(request, "users/contact_us.html", context)


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


def _activation_email_panel_context(
    profile: UserProfile,
    feedback_message: str = "",
    feedback_level: str = "info",
) -> dict:
    return {
        "show_send_activation_button": not profile.email_confirmed,
        "activation_feedback_message": feedback_message,
        "activation_feedback_level": feedback_level,
    }


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
            login(request, user)
            invited_community = _consume_pending_invite(request, user)
            notification_signals.email_verification_needed.send_robust(
                sender=type(user),
                user=user,
            )
            try:
                send_account_activation_email(request, user)
                messages.success(
                    request,
                    "Registration successful. Check your email to activate your "
                    "account.",
                    extra_tags="auth",
                )
            except Exception:
                messages.error(
                    request,
                    "Account created, but activation email could not be sent. "
                    "Please contact support.",
                    extra_tags="auth",
                )

            target_url = reverse("index")
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                target_url = reverse(
                    "community-canvas",
                    kwargs={"slug": invited_community.slug},
                )

            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=200)
                response["HX-Redirect"] = target_url
                return response

            return redirect(target_url)
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
            user = form.get_user()
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            invited_community = _consume_pending_invite(
                request,
                user,
            )
            messages.success(
                request,
                "Logged in successfully.",
                extra_tags="auth",
            )
            if not profile.email_confirmed:
                notification_signals.email_verification_needed.send_robust(
                    sender=type(user),
                    user=user,
                )
                messages.info(
                    request,
                    "Your email is not confirmed yet. You can browse the app, "
                    "but chat messages and community creation are disabled until "
                    "you confirm it.",
                )
            target_url = reverse("index")
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                target_url = reverse(
                    "community-canvas",
                    kwargs={"slug": invited_community.slug},
                )

            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=200)
                response["HX-Redirect"] = target_url
                return response

            return redirect(target_url)
        username = str(request.POST.get("username", "")).strip()
        password = str(request.POST.get("password", ""))
        if username and password:
            candidate_user = User.objects.filter(username__iexact=username).first()
            if candidate_user is not None and candidate_user.check_password(password):
                if not candidate_user.is_active:
                    form.add_error(
                        None,
                        "Your account is disabled in the authentication system. "
                        "Run the latest migrations or activate your account again.",
                    )
    else:
        form = LoginForm(request)

    context = {"form": form}
    context.update(_base_nav_context(request))
    return render(request, "users/login.html", context)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(
        request,
        "You have been logged out.",
        extra_tags="auth",
    )
    return redirect("index")


@login_required
def profile_settings_view(request: HttpRequest) -> HttpResponse:
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    previous_password_hash = user.password

    if request.method == "POST":
        form = ProfileSettingsForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            email_changed = form.email_changed()
            updated_user = form.save()
            if updated_user.password != previous_password_hash:
                update_session_auth_hash(request, updated_user)

            if email_changed:
                new_email = form.cleaned_data["email"].strip().lower()
                try:
                    send_email_verification_email(request, user, new_email)
                    notification_signals.email_change_verification_needed.send_robust(
                        sender=type(user),
                        user=user,
                        new_email=new_email,
                    )
                    messages.success(
                        request,
                        f"Profile updated successfully. Verification email sent to "
                        f"{new_email}. Please verify your new email address to update "
                        f"your account.",
                        extra_tags="profile",
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Profile updated, but verification email could not be sent. "
                        "Please try resending it later.",
                        extra_tags="profile",
                    )
            else:
                messages.success(
                    request,
                    "Profile updated successfully.",
                    extra_tags="profile",
                )
            return redirect("profile-settings")
    else:
        form = ProfileSettingsForm(user=user)

    avatar_upload_form = AvatarUploadForm()

    avatar_url = ""
    if profile and profile.avatar_thumbnail:
        avatar_url = profile.avatar_thumbnail.url
    elif profile and profile.avatar:
        avatar_url = profile.avatar.url

    return render(
        request,
        "users/profile_settings.html",
        {
            "form": form,
            "avatar_upload_form": avatar_upload_form,
            "avatar_url": avatar_url,
            "active_tab": None,
            "canvas_url": "/",
            "leaders_url": "/leaders/",
            "guide_url": "/guide/",
            "communities_url": "/communities/",
            "pending_email": profile.pending_email or "",
            **_activation_email_panel_context(profile),
        },
    )


@login_required
@require_POST
def upload_avatar_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = AvatarUploadForm(request.POST, request.FILES)
    context = {
        "avatar_url": (
            profile.avatar_thumbnail.url
            if profile.avatar_thumbnail
            else (profile.avatar.url if profile.avatar else "")
        ),
        "avatar_upload_form": form,
        "avatar_upload_success": False,
    }

    if form.is_valid():
        profile.avatar = form.cleaned_data["avatar"]
        profile.save(update_fields=["avatar", "avatar_thumbnail"])
        context["avatar_url"] = (
            profile.avatar_thumbnail.url
            if profile.avatar_thumbnail
            else profile.avatar.url
        )
        context["avatar_upload_success"] = True

    return render(request, "users/partials/avatar_upload_response.html", context)


@login_required
@require_POST
def resend_activation_email_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    feedback_message = ""
    feedback_level = "info"

    if profile.email_confirmed:
        feedback_message = "Your email is already confirmed."
        feedback_level = "info"
        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "users/partials/activation_email_panel.html",
                _activation_email_panel_context(
                    profile,
                    feedback_message=feedback_message,
                    feedback_level=feedback_level,
                ),
            )
        messages.info(request, feedback_message, extra_tags="profile")
        return redirect("profile-settings")

    try:
        send_account_activation_email(request, request.user)
        feedback_message = "Activation email has been sent. Please check your inbox."
        feedback_level = "success"
    except Exception:
        feedback_message = "Could not send activation email right now. Please try again later."
        feedback_level = "error"

    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "users/partials/activation_email_panel.html",
            _activation_email_panel_context(
                profile,
                feedback_message=feedback_message,
                feedback_level=feedback_level,
            ),
        )

    if feedback_level == "success":
        messages.success(request, feedback_message, extra_tags="profile")
    elif feedback_level == "error":
        messages.error(request, feedback_message, extra_tags="profile")
    else:
        messages.info(request, feedback_message, extra_tags="profile")

    return redirect("profile-settings")


def activate_account_view(
    request: HttpRequest,
    uidb64: str,
    token: str,
) -> HttpResponse:
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None:
        messages.error(
            request,
            "Invalid activation link.",
            extra_tags="auth",
        )
        return redirect("login")

    profile, _ = UserProfile.objects.get_or_create(user=user)

    if profile.email_confirmed:
        return redirect("activation-success")

    if not default_token_generator.check_token(user, token):
        messages.error(
            request,
            "Activation link is invalid or expired.",
            extra_tags="auth",
        )
        return redirect("login")

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

    profile.email_confirmed = True
    profile.save(update_fields=["email_confirmed"])
    notification_signals.email_confirmed.send_robust(
        sender=type(user),
        user=user,
    )
    return redirect("activation-success")


def verify_email_change_view(request: HttpRequest, token: str) -> HttpResponse:
    from .email_service import get_user_from_email_verify_token

    user, new_email = get_user_from_email_verify_token(token)
    if user is None or not new_email:
        messages.error(
            request,
            "Email verification link is invalid or expired.",
            extra_tags="auth",
        )
        return redirect("login")

    profile, _ = UserProfile.objects.get_or_create(user=user)

    # User cancelled the email change after the link was sent.
    if not profile.pending_email or profile.pending_email.lower() != new_email.lower():
        if request.user.is_authenticated:
            messages.info(
                request,
                "This email change request was already cancelled and the link is"
                " no longer valid.",
                extra_tags="profile",
            )
            return redirect("profile-settings")
        messages.info(
            request,
            "This email change request was already cancelled.",
            extra_tags="auth",
        )
        return redirect("login")

    existing_user = User.objects.filter(
        email__iexact=new_email
    ).exclude(pk=user.pk).first()
    if existing_user is not None:
        messages.error(
            request,
            "This email address is already registered to another account.",
            extra_tags="auth",
        )
        return redirect("login")

    user.email = new_email
    user.save(update_fields=["email"])

    profile.pending_email = ""
    profile.email_confirmed = True
    profile.save(update_fields=["pending_email", "email_confirmed"])

    notification_signals.email_confirmed.send_robust(
        sender=type(user),
        user=user,
    )

    if not request.user.is_authenticated:
        messages.success(
            request,
            "Email verified successfully. You can now log in with your new email.",
            extra_tags="auth",
        )
        return redirect("login")

    messages.success(
        request,
        "Your email address has been updated successfully.",
        extra_tags="profile",
    )
    return redirect("profile-settings")


@login_required
@require_POST
def cancel_email_change_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.pending_email:
        profile.pending_email = ""
        profile.save(update_fields=["pending_email"])
        messages.success(
            request,
            "Email change cancelled. Your current email address remains unchanged.",
            extra_tags="profile",
        )
    return redirect("profile-settings")


def activation_success_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "users/activation_success.html",
        _base_nav_context(request),
    )


def _user_from_identifier(identifier: str) -> User | None:
    value = str(identifier).strip()
    if not value:
        return None

    return User.objects.filter(Q(email__iexact=value) |
                               Q(username__iexact=value)).first()


def forgot_password_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            user = _user_from_identifier(form.cleaned_data["identifier"])
            if user is not None:
                try:
                    send_password_reset_email(request, user)
                except Exception:
                    messages.error(
                        request,
                        "Could not send password reset email right now. "
                        "Please try again later.",
                    )
                    return redirect("forgot-password")

            messages.success(
                request,
                "If this account exists, a password reset link has been "
                "sent to its email address.",
            )
            return redirect("login")
    else:
        form = ForgotPasswordForm()

    context = {"form": form}
    context.update(_base_nav_context(request))
    return render(request, "users/forgot_password.html", context)


def password_reset_confirm_view(request: HttpRequest, token: str) -> HttpResponse:
    user = get_user_from_password_reset_token(token)
    if user is None:
        messages.error(
            request,
            "Password reset link is invalid or expired.",
            extra_tags="auth",
        )
        return redirect("forgot-password")

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Password changed successfully. Please login again.",
            )
            return redirect("login")
    else:
        form = SetPasswordForm(user)

    context = {
        "form": form,
    }
    context.update(_base_nav_context(request))
    return render(request, "users/reset_password.html", context)
