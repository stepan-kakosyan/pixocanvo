import base64
import hashlib
import hmac

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from Notifications import signals as notification_signals
from pixelwar.models import (
    Community,
    CommunityMembership,
    compact_legacy_invite_uuid,
)

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
from .models import ContactMessage, PixoTransaction, UserProfile
from .models import ReferralAttribution
from .pixo_service import (
    assign_referrer_if_missing,
    grant_email_verification_pixo,
    grant_referral_community_join_reward,
)
from django.db.models import Q

PERSONAL_REFERRAL_TOKEN_SALT = "users.personal_referral.v1"
PERSONAL_REFERRAL_SIG_HEX_LEN = 12


def _base_nav_context(request: HttpRequest) -> dict:
    return {
        "active_tab": None,
        "layout": (
            "partial"
            if request.headers.get("HX-Request") == "true"
            else "full"
        ),
    }


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes | None:
    value = str(raw or "").strip()
    if not value:
        return None
    padding = "=" * ((4 - (len(value) % 4)) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError):
        return None


def _referral_signature(payload: str) -> str:
    secret = (
        f"{settings.SECRET_KEY}:{PERSONAL_REFERRAL_TOKEN_SALT}"
    ).encode("utf-8")
    digest = hmac.new(
        secret,
        str(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:PERSONAL_REFERRAL_SIG_HEX_LEN]


def _encode_personal_referral_token(user: User | None) -> str:
    if not user or not getattr(user, "id", None):
        return ""
    raw_payload = "|".join([
        str(int(user.id)),
        str(user.username or "").strip(),
        str(user.email or "").strip().lower(),
    ])
    payload = _b64url_encode(raw_payload.encode("utf-8"))
    return f"{payload}.{_referral_signature(payload)}"


def _decode_personal_referral_token(token: str | None) -> dict | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None

    payload, signature = raw.rsplit(".", 1)
    expected_signature = _referral_signature(payload)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    decoded = _b64url_decode(payload)
    if decoded is None:
        return None

    try:
        uid_raw, username, email = decoded.decode("utf-8").split("|", 2)
        uid = int(uid_raw)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None

    if uid <= 0:
        return None

    return {
        "uid": uid,
        "username": str(username or "").strip(),
        "email": str(email or "").strip().lower(),
    }


def _resolve_personal_referrer_user(ref_raw: str | None) -> User | None:
    token_payload = _decode_personal_referral_token(ref_raw)
    if token_payload is not None:
        user = User.objects.filter(pk=token_payload["uid"]).first()
        if user is None:
            return None

        expected_username = token_payload["username"]
        expected_email = token_payload["email"]
        if expected_username and user.username != expected_username:
            return None
        if expected_email and user.email.strip().lower() != expected_email:
            return None
        return user

    # Backward compatibility: old plain integer referral links.
    try:
        referrer_id = int(str(ref_raw or "").strip())
    except (TypeError, ValueError):
        return None
    if referrer_id <= 0:
        return None
    return User.objects.filter(pk=referrer_id).first()


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
    pending_referrer_user_id = request.session.pop("pending_referrer_user_id", None)
    pending_referral_source = request.session.pop("pending_referral_source", "")
    pending_referral_community_id = request.session.pop(
        "pending_referral_community_id",
        None,
    )

    referrer_user = None
    if pending_referrer_user_id:
        referrer_user = User.objects.filter(pk=pending_referrer_user_id).first()

    if not token:
        if referrer_user and referrer_user.id != user.id:
            assign_referrer_if_missing(
                referred_user=user,
                referrer_user=referrer_user,
                source=(
                    pending_referral_source
                    or ReferralAttribution.SOURCE_PERSONAL_LINK
                ),
                community=(
                    Community.objects.filter(pk=pending_referral_community_id).first()
                    if pending_referral_community_id
                    else None
                ),
            )
        return None

    community = Community.objects.filter(invite_token=token).first()
    if community is None:
        compact = compact_legacy_invite_uuid(token)
        if compact:
            community = Community.objects.filter(invite_token=compact).first()
    if community is None:
        return None

    membership, created = CommunityMembership.objects.get_or_create(
        community=community,
        user=user,
        defaults={"active": True},
    )
    if created and referrer_user and referrer_user.id != user.id:
        grant_referral_community_join_reward(
            invited_user=user,
            referrer_user=referrer_user,
            community=community,
        )
    elif referrer_user and referrer_user.id != user.id:
        assign_referrer_if_missing(
            referred_user=user,
            referrer_user=referrer_user,
            source=(
                pending_referral_source
                or ReferralAttribution.SOURCE_COMMUNITY_INVITE
            ),
            community=community,
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


def _queue_pixo_reward_modal(
    request: HttpRequest,
    *,
    amount: int,
    balance: int,
    details: str,
) -> None:
    request.session["pixo_reward_modal"] = {
        "amount": int(amount),
        "balance": int(balance),
        "details": str(details),
        "title": "Congratulations!",
    }
    request.session.modified = True


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

            target_url = str(reverse_lazy("index"))
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                target_url = str(reverse_lazy(
                    "community-canvas",
                    kwargs={"slug": invited_community.slug},
                ))

            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=200)
                response["HX-Redirect"] = target_url
                return response

            return redirect(target_url)
    else:
        ref_raw = request.GET.get("ref")
        referrer_user = _resolve_personal_referrer_user(ref_raw)
        if referrer_user is not None:
            request.session["pending_referrer_user_id"] = int(referrer_user.id)
            request.session[
                "pending_referral_source"
            ] = ReferralAttribution.SOURCE_PERSONAL_LINK
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
            target_url = str(reverse_lazy("index"))
            if invited_community is not None:
                messages.success(
                    request,
                    f"You joined '{invited_community.name}'.",
                )
                target_url = str(reverse_lazy(
                    "community-canvas",
                    kwargs={"slug": invited_community.slug},
                ))

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
        ref_raw = request.GET.get("ref")
        referrer_user = _resolve_personal_referrer_user(ref_raw)
        if referrer_user is not None:
            request.session["pending_referrer_user_id"] = int(referrer_user.id)
            request.session[
                "pending_referral_source"
            ] = ReferralAttribution.SOURCE_PERSONAL_LINK
        form = LoginForm(request)

    context = {"form": form}
    context.update(_base_nav_context(request))
    return render(request, "users/login.html", context)


def personal_referral_redirect_view(
    request: HttpRequest,
    token: str,
) -> HttpResponse:
    referrer_user = _resolve_personal_referrer_user(token)
    if referrer_user is None:
        messages.error(
            request,
            _("Referral link is invalid."),
            extra_tags="auth",
        )
        return redirect("register")

    if request.user.is_authenticated:
        if request.user.id == referrer_user.id:
            messages.error(
                request,
                _("Self-referral is not allowed."),
                extra_tags="auth",
            )
            return redirect("index")

        assign_referrer_if_missing(
            referred_user=request.user,
            referrer_user=referrer_user,
            source=ReferralAttribution.SOURCE_PERSONAL_LINK,
            community=None,
        )
        messages.success(
            request,
            _("Referral was registered."),
            extra_tags="auth",
        )
        return redirect("index")

    request.session["pending_referrer_user_id"] = int(referrer_user.id)
    request.session[
        "pending_referral_source"
    ] = ReferralAttribution.SOURCE_PERSONAL_LINK
    return redirect("register")


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
            "rewarded_pixels_count": int(profile.rewarded_pixels_count) if profile else 0,
            "personal_referral_link": request.build_absolute_uri(
                reverse_lazy(
                    "personal-referral",
                    kwargs={
                        "token": _encode_personal_referral_token(request.user),
                    },
                )
            ),
            "active_tab": None,
            "canvas_url": reverse_lazy("index"),
            "leaders_url": reverse_lazy("leaders"),
            "guide_url": reverse_lazy("guide"),
            "communities_url": reverse_lazy("communities"),
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
        "rewarded_pixels_count": int(profile.rewarded_pixels_count),
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
    reward = grant_email_verification_pixo(user)
    if reward:
        _queue_pixo_reward_modal(
            request,
            amount=reward["amount"],
            balance=reward["balance"],
            details=reward["details"],
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
    reward = grant_email_verification_pixo(user)
    if reward:
        _queue_pixo_reward_modal(
            request,
            amount=reward["amount"],
            balance=reward["balance"],
            details=reward["details"],
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


@login_required
def pixo_transactions_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    transactions_qs = PixoTransaction.objects.filter(profile=profile).order_by(
        "-created_at", "-id"
    )

    paginator = Paginator(transactions_qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "transactions": page_obj.object_list,
        "pixo_balance": profile.pixo_balance,
    }
    context.update(_base_nav_context(request))
    return render(request, "users/pixo_transactions.html", context)


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
