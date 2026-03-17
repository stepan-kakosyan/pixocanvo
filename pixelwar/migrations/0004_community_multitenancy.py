from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def seed_default_community(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Community = apps.get_model("pixelwar", "Community")
    CommunityMembership = apps.get_model("pixelwar", "CommunityMembership")
    Pixel = apps.get_model("pixelwar", "Pixel")
    UserAction = apps.get_model("pixelwar", "UserAction")
    ChatMessage = apps.get_model("pixelwar", "ChatMessage")

    owner = User.objects.order_by("id").first()
    if owner is None:
        owner = User.objects.create_user(
            username="community-owner",
            email="owner@example.com",
            password=User.objects.make_random_password(),
        )

    community, _created = Community.objects.get_or_create(
        slug="global",
        defaults={
            "name": "Global",
            "owner_id": owner.id,
            "invite_token": uuid.uuid4(),
        },
    )

    Pixel.objects.filter(community__isnull=True).update(community_id=community.id)
    UserAction.objects.filter(community__isnull=True).update(
        community_id=community.id
    )
    ChatMessage.objects.filter(community__isnull=True).update(
        community_id=community.id
    )

    CommunityMembership.objects.get_or_create(
        community_id=community.id,
        user_id=owner.id,
        defaults={"active": True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0003_chatmessage"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Community",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64, unique=True)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                (
                    "invite_token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_communities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="CommunityMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
                (
                    "community",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="pixelwar.community",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="pixel",
            name="community",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pixels",
                to="pixelwar.community",
            ),
        ),
        migrations.AddField(
            model_name="useraction",
            name="community",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="actions",
                to="pixelwar.community",
            ),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="community",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chat_messages",
                to="pixelwar.community",
            ),
        ),
        migrations.RunPython(seed_default_community, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pixel",
            name="community",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pixels",
                to="pixelwar.community",
            ),
        ),
        migrations.AlterField(
            model_name="useraction",
            name="community",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="actions",
                to="pixelwar.community",
            ),
        ),
        migrations.AlterField(
            model_name="chatmessage",
            name="community",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chat_messages",
                to="pixelwar.community",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="pixel",
            name="uniq_pixel_coord",
        ),
        migrations.RemoveIndex(
            model_name="pixel",
            name="pixelwar_pix_x_aeb838_idx",
        ),
        migrations.RemoveIndex(
            model_name="useraction",
            name="pixelwar_us_user_ke_6c2e9a_idx",
        ),
        migrations.AddConstraint(
            model_name="communitymembership",
            constraint=models.UniqueConstraint(
                fields=("community", "user"),
                name="uniq_community_member",
            ),
        ),
        migrations.AddConstraint(
            model_name="pixel",
            constraint=models.UniqueConstraint(
                fields=("community", "x", "y"),
                name="uniq_pixel_coord_in_community",
            ),
        ),
        migrations.AddIndex(
            model_name="communitymembership",
            index=models.Index(
                fields=["user", "active"],
                name="pixelwar_co_user_id_c72e78_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pixel",
            index=models.Index(
                fields=["community", "x", "y"],
                name="pixelwar_pi_communi_d5af66_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="useraction",
            index=models.Index(
                fields=["community", "user_key", "created_at"],
                name="pixelwar_us_communi_736ed9_idx",
            ),
        ),
    ]
