# Generated migration for adding thumbnail image field to Community

from django.db import migrations, models
import pixelwar.models


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0008_community_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="image_thumbnail",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=pixelwar.models.community_image_thumbnail_upload_path,
            ),
        ),
    ]
