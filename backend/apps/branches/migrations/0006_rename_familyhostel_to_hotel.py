"""Data migration: rename branches whose name starts with
``Family Hostel — `` to use ``Hotel — `` instead.

Part of the FamilyHostel → Hotel rebrand (April 2026 refactor). Pure
data migration; the schema is unchanged.
"""

from django.db import migrations


OLD_PREFIX = "Family Hostel — "
NEW_PREFIX = "Hotel — "


def rename_forward(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.filter(name__startswith=OLD_PREFIX):
        branch.name = NEW_PREFIX + branch.name[len(OLD_PREFIX):]
        branch.save(update_fields=["name"])


def rename_backward(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.filter(name__startswith=NEW_PREFIX):
        branch.name = OLD_PREFIX + branch.name[len(NEW_PREFIX):]
        branch.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0005_branch_monthly_expense_limit"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
