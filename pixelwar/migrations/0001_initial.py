from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Pixel",
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
                ("x", models.PositiveIntegerField()),
                ("y", models.PositiveIntegerField()),
                ("color", models.CharField(default="#FFFFFF", max_length=7)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="UserAction",
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
                ("user_key", models.CharField(db_index=True, max_length=128)),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("x", models.PositiveIntegerField()),
                ("y", models.PositiveIntegerField()),
                ("color", models.CharField(max_length=7)),
                ("accepted", models.BooleanField(default=False)),
                ("rejection_reason", models.CharField(blank=True, max_length=64)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="pixel",
            constraint=models.UniqueConstraint(
                fields=("x", "y"),
                name="uniq_pixel_coord",
            ),
        ),
        migrations.AddIndex(
            model_name="pixel",
            index=models.Index(fields=["x", "y"], name="pixelwar_pix_x_aeb838_idx"),
        ),
        migrations.AddIndex(
            model_name="useraction",
            index=models.Index(
                fields=["user_key", "created_at"],
                name="pixelwar_us_user_ke_6c2e9a_idx",
            ),
        ),
    ]
