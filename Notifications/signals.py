from django.dispatch import Signal, receiver
from django.utils.translation import gettext as _

from .models import Notification
from .services import community_notification_visual
from .services import system_notification_visual
from .services import user_notification_visual
from .tasks import create_notification_task

# Domain-level notification events emitted by other apps.
email_verification_needed = Signal()
email_confirmed = Signal()
email_change_verification_needed = Signal()  # kwargs: user, new_email
community_join_requested = Signal()
community_join_reviewed = Signal()


@receiver(email_verification_needed)
def on_email_verification_needed(sender, user, **kwargs):
    system_visual = system_notification_visual()
    create_notification_task.delay(
        recipient_id=user.id,
        notification_type=Notification.TYPE_SYSTEM_NOTICE,
        title=_("Confirm your email"),
        body=_(
            "Validate your email to unlock chat and community creation. "
            "If you did not receive the email, open Profile Details and resend it."
        ),
        target_url="/auth/profile/",
        visual_type=system_visual["visual_type"],
        image_url=system_visual["image_url"],
        initials=system_visual["initials"],
    )


@receiver(email_change_verification_needed)
def on_email_change_verification_needed(sender, user, new_email, **kwargs):
    system_visual = system_notification_visual()
    create_notification_task.delay(
        recipient_id=user.id,
        notification_type=Notification.TYPE_EMAIL_CHANGE_PENDING,
        title=_("Verify your new email"),
        body=_(
            "You requested to change your email to %(email)s. "
            "We've sent a verification link there — click it to confirm the update."
        ) % {"email": new_email},
        target_url="/auth/profile/",
        visual_type=system_visual["visual_type"],
        image_url=system_visual["image_url"],
        initials=system_visual["initials"],
    )


@receiver(email_confirmed)
def on_email_confirmed(sender, user, **kwargs):
    system_visual = system_notification_visual()
    create_notification_task.delay(
        recipient_id=user.id,
        notification_type=Notification.TYPE_EMAIL_CONFIRMED,
        title=_("Email confirmed"),
        body=_("Congratulations. Your email has been confirmed successfully."),
        target_url="",
        visual_type=system_visual["visual_type"],
        image_url=system_visual["image_url"],
        initials=system_visual["initials"],
    )


@receiver(community_join_requested)
def on_community_join_requested(sender, requester, community, **kwargs):
    requester_visual = user_notification_visual(requester)
    create_notification_task.delay(
        recipient_id=community.owner_id,
        notification_type=Notification.TYPE_JOIN_REQUEST,
        title=_("New join request"),
        body=_("%(username)s requested to join %(community)s.")
        % {
            "username": requester.username,
            "community": community.name,
        },
        target_url=f"/comunity/{community.slug}/details/",
        visual_type=requester_visual["visual_type"],
        image_url=requester_visual["image_url"],
        initials=requester_visual["initials"],
    )


@receiver(community_join_reviewed)
def on_community_join_reviewed(
    sender,
    requester,
    community,
    approved,
    **kwargs,
):
    community_visual = community_notification_visual(community)
    create_notification_task.delay(
        recipient_id=requester.id,
        notification_type=(
            Notification.TYPE_JOIN_APPROVED
            if approved
            else Notification.TYPE_JOIN_DECLINED
        ),
        title=_("Join request approved") if approved else _("Join request declined"),
        body=(
            _("Your request to join %(community)s was approved.")
            if approved
            else _("Your request to join %(community)s was declined.")
        )
        % {
            "community": community.name,
        },
        target_url=f"/comunity/{community.slug}/details/",
        visual_type=community_visual["visual_type"],
        image_url=community_visual["image_url"],
        initials=community_visual["initials"],
    )
