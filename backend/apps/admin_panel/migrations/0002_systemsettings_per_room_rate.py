"""Add per_room_rate field to SystemSettings."""

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="per_room_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=12,
            ),
        ),
    ]
