"""Add passport_number to Client (required for walk-in guests)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_salary_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="passport_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Passport / ID document number. Required for walk-in "
                    "guests; may be blank for legacy or telegram-only clients."
                ),
                max_length=50,
                null=True,
                unique=True,
            ),
        ),
    ]
