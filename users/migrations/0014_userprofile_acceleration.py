# Migration for acceleration feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0013_rename_users_refer_referre_17821b_idx_users_refer_referre_55cea2_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='acceleration_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='acceleration_pixels_placed',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
