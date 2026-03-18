from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0005_rename_pixelwar_co_user_id_c72e78_idx_pixelwar_co_user_id_9a897e_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="community_covers/"),
        ),
        migrations.AddField(
            model_name="community",
            name="is_public",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="community",
            name="max_members",
            field=models.PositiveSmallIntegerField(
                choices=[(5, "5"), (10, "10"), (20, "20"), (30, "30"), (50, "50")],
                default=50,
            ),
        ),
        migrations.CreateModel(
            name="CommunityJoinRequest",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("declined", "Declined"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "community",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="join_requests",
                        to="pixelwar.community",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_join_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["community", "status"], name="pixelwar_co_communi_0ab325_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("community", "user"),
                        name="uniq_join_request_per_user_community",
                    )
                ],
            },
        ),
    ]
