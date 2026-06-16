"""Drop the SuspiciousActivity model + suspicious_activities table.

The whole detection / blocking subsystem has been removed; this migration
purges its leftover schema.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_client_date_of_birth"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SuspiciousActivity",
        ),
    ]
