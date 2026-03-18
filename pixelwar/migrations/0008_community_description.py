from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0007_rename_pixelwar_co_communi_0ab325_idx_pixelwar_co_communi_213219_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="description",
            field=models.CharField(blank=True, default="", max_length=280),
        ),
    ]
