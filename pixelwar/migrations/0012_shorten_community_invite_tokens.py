import base64
import uuid

from django.db import migrations, models
from django.utils.crypto import get_random_string


def _generate_invite_token():
    return get_random_string(
        length=22,
        allowed_chars=(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-_"
        ),
    )


def _compact_legacy_uuid(value):
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None
    token = base64.urlsafe_b64encode(parsed.bytes).decode("ascii")
    return token.rstrip("=")


def shorten_existing_invite_tokens(apps, schema_editor):
    Community = apps.get_model("pixelwar", "Community")

    used_tokens = set(
        Community.objects.values_list("invite_token", flat=True)
    )

    for community in Community.objects.all().only("id", "invite_token"):
        current = str(community.invite_token or "").strip()
        compact = _compact_legacy_uuid(current)
        if compact:
            if compact == current:
                continue
            if compact in used_tokens:
                continue
            Community.objects.filter(id=community.id).update(invite_token=compact)
            used_tokens.discard(current)
            used_tokens.add(compact)
            continue

        if current and len(current) <= 22:
            continue

        replacement = _generate_invite_token()
        while replacement in used_tokens:
            replacement = _generate_invite_token()
        Community.objects.filter(id=community.id).update(invite_token=replacement)
        used_tokens.discard(current)
        used_tokens.add(replacement)


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0011_remove_community_max_members"),
    ]

    operations = [
        migrations.RunPython(
            shorten_existing_invite_tokens,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="community",
            name="invite_token",
            field=models.CharField(
                default=_generate_invite_token,
                editable=False,
                max_length=22,
                unique=True,
            ),
        ),
    ]
