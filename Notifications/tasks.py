from celery import shared_task

from .services import create_notification


@shared_task
def create_notification_task(
    *,
    recipient_id: int,
    notification_type: str,
    title: str,
    body: str,
    target_url: str,
    visual_type: str,
    image_url: str,
    initials: str,
) -> None:
    create_notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        body=body,
        target_url=target_url,
        visual_type=visual_type,
        image_url=image_url,
        initials=initials,
    )
