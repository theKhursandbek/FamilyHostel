"""Add date_of_birth to Client (collected at registration)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_otp_tokens_and_phone_verified"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="date_of_birth",
            field=models.DateField(
                null=True,
                blank=True,
                help_text="Client's date of birth (collected at Mini App registration).",
            ),
        ),
    ]
