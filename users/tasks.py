from celery import shared_task

from .email_service import send_account_activation_email_payload
from .email_service import send_password_reset_email_payload


@shared_task
def send_account_activation_email_task(
    *,
    user_id: int,
    activation_url: str,
    language_code: str,
) -> None:
    send_account_activation_email_payload(
        user_id=user_id,
        activation_url=activation_url,
        language_code=language_code,
    )


@shared_task
def send_password_reset_email_task(
    *,
    user_id: int,
    reset_url: str,
    language_code: str,
) -> None:
    send_password_reset_email_payload(
        user_id=user_id,
        reset_url=reset_url,
        language_code=language_code,
    )
