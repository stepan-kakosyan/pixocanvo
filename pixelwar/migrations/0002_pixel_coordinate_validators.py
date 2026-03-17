from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pixelwar", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pixel",
            name="x",
            field=models.PositiveIntegerField(
                validators=[MinValueValidator(0), MaxValueValidator(999)]
            ),
        ),
        migrations.AlterField(
            model_name="pixel",
            name="y",
            field=models.PositiveIntegerField(
                validators=[MinValueValidator(0), MaxValueValidator(999)]
            ),
        ),
    ]
