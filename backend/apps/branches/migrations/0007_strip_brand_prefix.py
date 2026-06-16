"""Data migration: strip ``Hotel — `` / ``Family Hostel — `` prefix from
every Branch name so the user-facing label is just the district
(e.g. ``Yashnobod``). The brand name lives only in the sidebar.
"""

from django.db import migrations


PREFIXES = ("Hotel — ", "Family Hostel — ")


def strip_forward(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.all():
        for prefix in PREFIXES:
            if branch.name.startswith(prefix):
                branch.name = branch.name[len(prefix):]
                branch.save(update_fields=["name"])
                break


def restore_backward(apps, schema_editor):
    # Best-effort restore using the canonical "Hotel — " prefix.
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.all():
        if not any(branch.name.startswith(p) for p in PREFIXES):
            branch.name = f"Hotel — {branch.name}"
            branch.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0006_rename_familyhostel_to_hotel"),
    ]

    operations = [
        migrations.RunPython(strip_forward, restore_backward),
    ]
