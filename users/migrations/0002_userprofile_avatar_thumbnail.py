# Generated migration for adding thumbnail fields

from django.db import migrations, models
import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="avatar_thumbnail",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=users.models.avatar_thumbnail_upload_path,
            ),
        ),
    ]
