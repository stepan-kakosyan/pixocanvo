from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_reactivate_existing_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="pending_email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True
            ),
        ),
    ]
