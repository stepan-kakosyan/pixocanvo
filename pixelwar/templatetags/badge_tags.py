from django import template

register = template.Library()

# Ordered highest → lowest so the first match gives the highest tier.
BADGE_TIERS = [
    (1000, "legend",  "Legend — 1000+ pixels"),
    (500,  "elite",   "Elite — 500+ pixels"),
    (250,  "master",  "Master — 250+ pixels"),
    (100,  "artist",  "Artist — 100+ pixels"),
    (50,   "builder", "Builder — 50+ pixels"),
    (10,   "rookie",  "Rookie — 10+ pixels"),
]


@register.inclusion_tag("pixelwar/partials/achievement_badge.html")
def achievement_badge(pixel_count, position="br"):
    """Render an achievement badge overlay for a user avatar.

    pixel_count: UserProfile.rewarded_pixels_count value.
    position:    'br' = bottom-right (default), 'tr' = top-right.
    """
    tier_name = None
    tier_label = None
    for threshold, name, label in BADGE_TIERS:
        if (pixel_count or 0) >= threshold:
            tier_name = name
            tier_label = label
            break
    return {"tier": tier_name, "tier_label": tier_label, "position": position}
