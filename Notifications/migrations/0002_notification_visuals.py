from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="image_url",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="notification",
            name="initials",
            field=models.CharField(blank=True, default="", max_length=4),
        ),
        migrations.AddField(
            model_name="notification",
            name="visual_type",
            field=models.CharField(
                choices=[
                    ("system", "System"),
                    ("user", "User"),
                    ("community", "Community"),
                ],
                default="system",
                max_length=16,
            ),
        ),
    ]
