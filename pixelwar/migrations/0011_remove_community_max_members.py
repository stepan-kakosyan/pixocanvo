from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0010_alter_community_image"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="community",
            name="max_members",
        ),
    ]
