from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from pixelwar.models import UserAction
from pixelwar.models import Community

from .models import PixoTransaction, ReferralAttribution, UserProfile

EMAIL_VERIFICATION_REWARD = 75
PIXEL_MILESTONES: tuple[tuple[int, int], ...] = (
    (10, 10),
    (50, 20),
    (100, 30),
    (250, 50),
    (500, 80),
    (1000, 100),
)
POST_1000_STEP = 500
POST_1000_REWARD = 50
COMMUNITY_JOIN_REFERRAL_REWARD = 1
MILESTONE_10_REFERRAL_REWARD = 5


def _award_once(
    profile: UserProfile,
    *,
    amount: int,
    reason: str,
    context_key: str,
    details: str,
) -> dict | None:
    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        balance_before = int(profile.pixo_balance)
        balance_after = balance_before + int(amount)

        reward, created = PixoTransaction.objects.get_or_create(
            context_key=context_key,
            defaults={
                "profile": profile,
                "amount": int(amount),
                "reason": reason,
                "details": details,
                "metadata": {},
            },
        )
        if not created:
            return None

        profile.pixo_balance = balance_after
        profile.save(update_fields=["pixo_balance"])

        def _send_reward_notification() -> None:
            from Notifications.models import Notification
            from Notifications.services import system_notification_visual
            from Notifications.tasks import create_notification_task

            visual = system_notification_visual()
            create_notification_task.delay(
                recipient_id=profile.user_id,
                notification_type=Notification.TYPE_SYSTEM_NOTICE,
                title="Congratulations!",
                body=(
                    f"You received {int(amount)} Pixo. "
                    f"{details}. Current balance: {balance_after} Pixo."
                ),
                target_url="/auth/pixo/",
                visual_type=visual["visual_type"],
                image_url=visual["image_url"],
                initials=visual["initials"],
            )

        transaction.on_commit(_send_reward_notification)
        profile.refresh_from_db(fields=["pixo_balance", "rewarded_pixels_count"])

    return {
        "amount": int(amount),
        "reason": reason,
        "details": details,
        "balance": int(profile.pixo_balance),
    }


def grant_email_verification_pixo(user: User) -> dict | None:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return _award_once(
        profile,
        amount=EMAIL_VERIFICATION_REWARD,
        reason=PixoTransaction.REASON_EMAIL_VERIFIED,
        context_key=f"email-verified:{user.id}",
        details="Email verification reward",
    )


def assign_referrer_if_missing(
    *,
    referred_user: User,
    referrer_user: User,
    source: str,
    community: Community | None = None,
) -> ReferralAttribution | None:
    if referred_user.id == referrer_user.id:
        return None

    attribution, created = ReferralAttribution.objects.get_or_create(
        referred_user=referred_user,
        defaults={
            "referrer_user": referrer_user,
            "source": source,
            "community": community,
        },
    )
    if created:
        return attribution
    return attribution


def grant_referral_community_join_reward(
    *,
    invited_user: User,
    referrer_user: User,
    community: Community,
) -> dict | None:
    if invited_user.id == referrer_user.id:
        return None

    assign_referrer_if_missing(
        referred_user=invited_user,
        referrer_user=referrer_user,
        source=ReferralAttribution.SOURCE_COMMUNITY_INVITE,
        community=community,
    )

    referrer_profile, _ = UserProfile.objects.get_or_create(user=referrer_user)
    return _award_once(
        referrer_profile,
        amount=COMMUNITY_JOIN_REFERRAL_REWARD,
        reason=PixoTransaction.REASON_REFERRAL_COMMUNITY_JOIN,
        context_key=f"referral-community-join:{community.id}:{invited_user.id}",
        details=(
            f"{invited_user.username} joined {community.name} via your invitation"
        ),
    )


def grant_referral_milestone_reward_if_eligible(
    *,
    referred_user: User,
    total_accepted_pixels: int,
) -> dict | None:
    if int(total_accepted_pixels) < 10:
        return None

    attribution = (
        ReferralAttribution.objects.select_related("referrer_user")
        .filter(referred_user=referred_user)
        .first()
    )
    if attribution is None or attribution.milestone_10_rewarded_at is not None:
        return None
    if attribution.referrer_user_id == referred_user.id:
        return None

    referrer_profile, _ = UserProfile.objects.get_or_create(
        user=attribution.referrer_user
    )
    reward = _award_once(
        referrer_profile,
        amount=MILESTONE_10_REFERRAL_REWARD,
        reason=PixoTransaction.REASON_REFERRAL_MILESTONE,
        context_key=(
            f"referral-milestone-10:{attribution.referrer_user_id}:{referred_user.id}"
        ),
        details=(
            f"Referral milestone: {referred_user.username} reached 10 accepted pixels"
        ),
    )
    if reward is None:
        return None

    updated = ReferralAttribution.objects.filter(
        pk=attribution.pk,
        milestone_10_rewarded_at__isnull=True,
    ).update(milestone_10_rewarded_at=timezone.now())
    if not updated:
        return None

    return reward


def grant_pixel_milestones_pixo(user: User) -> list[dict]:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    total_accepted_pixels = UserAction.objects.filter(
        user_key=f"user:{user.id}",
        accepted=True,
    ).count()

    rewards: list[dict] = []

    for threshold, amount in PIXEL_MILESTONES:
        if total_accepted_pixels < threshold:
            continue
        reward = _award_once(
            profile,
            amount=amount,
            reason=PixoTransaction.REASON_PIXEL_MILESTONE,
            context_key=f"pixel-milestone:{user.id}:{threshold}",
            details=f"Reached {threshold} pixels",
        )
        if reward:
            reward["threshold"] = int(threshold)
            rewards.append(reward)

    if total_accepted_pixels > 1000:
        extra_steps = (total_accepted_pixels - 1000) // POST_1000_STEP
        for step in range(1, extra_steps + 1):
            threshold = 1000 + (step * POST_1000_STEP)
            reward = _award_once(
                profile,
                amount=POST_1000_REWARD,
                reason=PixoTransaction.REASON_PIXEL_MILESTONE,
                context_key=f"pixel-milestone:{user.id}:{threshold}",
                details=f"Reached {threshold} pixels",
            )
            if reward:
                reward["threshold"] = int(threshold)
                rewards.append(reward)

    if rewards:
        max_threshold = max(int(item.get("threshold", 0)) for item in rewards)
        if max_threshold > int(profile.rewarded_pixels_count):
            UserProfile.objects.filter(pk=profile.pk).update(
                rewarded_pixels_count=max_threshold
            )

    grant_referral_milestone_reward_if_eligible(
        referred_user=user,
        total_accepted_pixels=total_accepted_pixels,
    )

    return rewards


def spend_pixo(
    user: User,
    *,
    amount: int,
    reason: str = PixoTransaction.REASON_FEATURE_SPEND,
    context_key: str,
    details: str = "",
    metadata: dict | None = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")

    profile, _ = UserProfile.objects.get_or_create(user=user)

    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        balance_before = int(profile.pixo_balance)
        if balance_before < int(amount):
            raise ValueError("insufficient_pixo")

        balance_after = balance_before - int(amount)

        tx, created = PixoTransaction.objects.get_or_create(
            context_key=context_key,
            defaults={
                "profile": profile,
                "amount": -int(amount),
                "reason": reason,
                "details": details,
                "metadata": metadata or {},
            },
        )
        if not created:
            current_balance = int(profile.pixo_balance)
            return {
                "amount": int(tx.amount),
                "reason": tx.reason,
                "details": tx.details,
                "balance": current_balance,
            }

        profile.pixo_balance = balance_after
        profile.save(update_fields=["pixo_balance"])

        def _send_spend_notification() -> None:
            from Notifications.models import Notification
            from Notifications.services import system_notification_visual
            from Notifications.tasks import create_notification_task

            visual = system_notification_visual()
            spend_details = details or "Pixo was spent"
            create_notification_task.delay(
                recipient_id=profile.user_id,
                notification_type=Notification.TYPE_SYSTEM_NOTICE,
                title="Pixo spent",
                body=(
                    f"{int(amount)} Pixo was deducted. "
                    f"{spend_details}. Current balance: {balance_after} Pixo."
                ),
                target_url="/auth/pixo/",
                visual_type=visual["visual_type"],
                image_url=visual["image_url"],
                initials=visual["initials"],
            )

        transaction.on_commit(_send_spend_notification)

    return {
        "amount": -int(amount),
        "reason": reason,
        "details": details,
        "balance": int(balance_after),
    }


ACCELERATION_COST = 15
ACCELERATION_PIXEL_LIMIT = 100
ACCELERATION_COOLDOWN_SECONDS = 10


def purchase_acceleration(user: User) -> dict:
    """Purchase acceleration: 10-second cooldown for next 100 pixels instead of 60.
    Raises ValueError if already active or insufficient pixo.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Check if already active
    if profile.acceleration_active and profile.acceleration_pixels_placed < ACCELERATION_PIXEL_LIMIT:
        raise ValueError("acceleration_already_active")

    # Attempt purchase
    try:
        spend_pixo(
            user,
            amount=ACCELERATION_COST,
            reason=PixoTransaction.REASON_FEATURE_SPEND,
            context_key=f"acceleration-purchase:{user.id}:{timezone.now().isoformat()}",
            details="Purchased acceleration (10s cooldown for 100 pixels)",
        )
    except ValueError as exc:
        if str(exc) == "insufficient_pixo":
            raise
        raise

    # Activate acceleration
    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        profile.acceleration_active = True
        profile.acceleration_pixels_placed = 0
        profile.save(update_fields=["acceleration_active", "acceleration_pixels_placed"])

    return {
        "success": True,
        "acceleration_active": True,
        "acceleration_pixels_remaining": ACCELERATION_PIXEL_LIMIT,
    }


def get_acceleration_status(user: User) -> dict:
    """Get current acceleration status."""
    profile, _ = UserProfile.objects.get_or_create(user=user)

    return {
        "acceleration_active": profile.acceleration_active,
        "acceleration_pixels_placed": profile.acceleration_pixels_placed,
        "acceleration_pixels_remaining": max(
            0,
            ACCELERATION_PIXEL_LIMIT - profile.acceleration_pixels_placed,
        ),
        "pixo_balance": profile.pixo_balance,
    }


def increment_acceleration_pixel_count(user: User) -> None:
    """Increment acceleration pixel count, deactivate if limit reached."""
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if not profile.acceleration_active:
        return

    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        if not profile.acceleration_active:
            return

        profile.acceleration_pixels_placed += 1
        if profile.acceleration_pixels_placed >= ACCELERATION_PIXEL_LIMIT:
            profile.acceleration_active = False

        profile.save(
            update_fields=["acceleration_pixels_placed", "acceleration_active"]
        )
