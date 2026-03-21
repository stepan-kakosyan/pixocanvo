from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_contactmessage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="avatar",
            field=models.ImageField(blank=True, null=True, upload_to="profile-avatars/"),
        ),
    ]
