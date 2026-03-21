from .models import UserProfile


def pixo_context(request):
    if not request.user.is_authenticated:
        return {
            "header_pixo_balance": 0,
            "header_rewarded_pixels_count": 0,
            "pixo_reward_modal": None,
        }

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Do not consume modal payload for htmx partial requests.
    if request.headers.get("HX-Request") == "true":
        reward_modal = request.session.get("pixo_reward_modal")
    else:
        reward_modal = request.session.pop("pixo_reward_modal", None)

    return {
        "header_pixo_balance": int(profile.pixo_balance),
        "header_rewarded_pixels_count": int(profile.rewarded_pixels_count),
        "pixo_reward_modal": reward_modal,
    }
