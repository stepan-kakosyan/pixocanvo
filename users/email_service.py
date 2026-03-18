from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def activation_base_url(request) -> str:
    domain = request.get_host().strip()
    protocol = getattr(request, "scheme", "https")

    if (
        (domain.startswith("localhost") or domain.startswith("127.0.0.1"))
        and ":" not in domain
    ):
        domain = f"{domain}:8000"

    return f"{protocol}://{domain}".rstrip("/")


def build_activation_url(request, user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_path = reverse(
        "activate-account",
        kwargs={"uidb64": uid, "token": token},
    )
    return f"{activation_base_url(request)}{activation_path}"


def _language_code_for_request(request) -> str:
    return (
        getattr(request, "LANGUAGE_CODE", "")
        or translation.get_language()
        or settings.LANGUAGE_CODE
    )


def send_account_activation_email_payload(
    *,
    user_id: int,
    activation_url: str,
    language_code: str,
) -> None:
    user = User.objects.filter(pk=user_id).first()
    if user is None or not user.email:
        return
    timeout_seconds = int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 86400))
    expires_in_hours = max(1, timeout_seconds // 3600)

    context = {
        "username": user.username,
        "activation_url": activation_url,
        "expires_in_hours": expires_in_hours,
        "LANGUAGE_CODE": language_code,
    }

    with translation.override(language_code):
        subject = _("Activate your account")
        text_body = render_to_string(
            "users/emails/account_activation.txt",
            context,
        )
        html_body = render_to_string(
            "users/emails/account_activation.html",
            context,
        )

    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        [user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_account_activation_email(request, user: User) -> None:
    from .tasks import send_account_activation_email_task

    activation_url = build_activation_url(request, user)
    send_account_activation_email_task.delay(
        user_id=user.id,
        activation_url=activation_url,
        language_code=_language_code_for_request(request),
    )


def _password_reset_signing_salt() -> str:
    return "users.password-reset"


def build_password_reset_token(user: User) -> str:
    return signing.dumps(
        {
            "uid": user.pk,
            "pwd": user.password,
        },
        salt=_password_reset_signing_salt(),
        compress=True,
    )


def get_user_from_password_reset_token(token: str) -> User | None:
    try:
        payload = signing.loads(
            token,
            salt=_password_reset_signing_salt(),
            max_age=settings.PASSWORD_RESET_LINK_TTL_SECONDS,
        )
    except signing.BadSignature:
        return None

    user_id = payload.get("uid")
    password_hash = payload.get("pwd")
    if user_id is None or not password_hash:
        return None

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return None
    if user.password != password_hash:
        return None
    return user


def build_password_reset_url(request, user: User) -> str:
    token = build_password_reset_token(user)
    reset_path = reverse(
        "password-reset-confirm",
        kwargs={"token": token},
    )
    return f"{activation_base_url(request)}{reset_path}"


def send_password_reset_email_payload(
    *,
    user_id: int,
    reset_url: str,
    language_code: str,
) -> None:
    user = User.objects.filter(pk=user_id).first()
    if user is None or not user.email:
        return
    timeout_seconds = int(
        getattr(settings, "PASSWORD_RESET_LINK_TTL_SECONDS", 1800)
    )
    expires_in_minutes = max(1, timeout_seconds // 60)

    context = {
        "username": user.username,
        "reset_url": reset_url,
        "expires_in_minutes": expires_in_minutes,
        "LANGUAGE_CODE": language_code,
    }

    with translation.override(language_code):
        subject = _("Reset your password")
        text_body = render_to_string(
            "users/emails/password_reset.txt",
            context,
        )
        html_body = render_to_string(
            "users/emails/password_reset.html",
            context,
        )

    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        [user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_password_reset_email(request, user: User) -> None:
    from .tasks import send_password_reset_email_task

    reset_url = build_password_reset_url(request, user)
    send_password_reset_email_task.delay(
        user_id=user.id,
        reset_url=reset_url,
        language_code=_language_code_for_request(request),
    )
