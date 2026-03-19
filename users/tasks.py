from celery import shared_task

from .email_service import send_account_activation_email_payload
from .email_service import send_contact_us_email_payload
from .email_service import send_password_reset_email_payload
from .email_service import send_email_verification_email_payload


TASK_RETRY_POLICY = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 3},
}


@shared_task(bind=True, **TASK_RETRY_POLICY)
def send_account_activation_email_task(
    self,
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


@shared_task(bind=True, **TASK_RETRY_POLICY)
def send_password_reset_email_task(
    self,
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


@shared_task(bind=True, **TASK_RETRY_POLICY)
def send_email_verification_email_task(
    self,
    *,
    user_id: int,
    new_email: str,
    verify_url: str,
    language_code: str,
) -> None:
    send_email_verification_email_payload(
        user_id=user_id,
        new_email=new_email,
        verify_url=verify_url,
        language_code=language_code,
    )


@shared_task(bind=True, **TASK_RETRY_POLICY)
def send_contact_us_email_task(
    self,
    *,
    contact_message_id: int,
    site_url: str,
    language_code: str,
) -> None:
    send_contact_us_email_payload(
        contact_message_id=contact_message_id,
        site_url=site_url,
        language_code=language_code,
    )
