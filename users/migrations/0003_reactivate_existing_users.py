from django.contrib.auth import get_user_model
from django.db import migrations


def reactivate_existing_users(apps, schema_editor):
    user_model = get_user_model()
    user_model.objects.filter(is_active=False).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_userprofile_email_confirmed"),
    ]

    operations = [
        migrations.RunPython(
            reactivate_existing_users,
            migrations.RunPython.noop,
        ),
    ]
