"""
Data migration — REFACTOR_PLAN_2026_04 \u00a77.2.

Convert legacy facility-log statuses to the new lifecycle:
    - 'open'      -> 'paid'  (existing logs already represent consummated
                              expenses; default payment_method to 'cash')
    - 'resolved'  -> 'resolved' (no change)
"""
from django.db import migrations


def forward(apps, schema_editor):
    FacilityLog = apps.get_model("reports", "FacilityLog")
    FacilityLog.objects.filter(status="open").update(
        status="paid", payment_method="cash",
    )


def backward(apps, schema_editor):
    FacilityLog = apps.get_model("reports", "FacilityLog")
    FacilityLog.objects.filter(status="paid").update(status="open")


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0008_facilitylog_approval_note_facilitylog_approved_at_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
