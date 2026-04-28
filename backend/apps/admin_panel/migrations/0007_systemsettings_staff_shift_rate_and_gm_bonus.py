"""
Phase 2 (REFACTOR_PLAN_2026_04 §5.1 + §5.2).

- Add ``SystemSettings.staff_shift_rate`` and copy data over from the
  pre-existing ``shift_rate`` column.
- Add ``SystemSettings.gm_bonus_percent`` (Decimal, default 0).

The legacy ``shift_rate`` column is kept for one release as a safety net
(model exposes it with a deprecation help_text). It will be dropped in the
§10 cleanup pass.
"""

from decimal import Decimal

from django.db import migrations, models


def copy_shift_rate_to_staff_shift_rate(apps, schema_editor):
    SystemSettings = apps.get_model("admin_panel", "SystemSettings")
    for row in SystemSettings.objects.all():
        if row.shift_rate is not None:
            row.staff_shift_rate = row.shift_rate
            row.save(update_fields=["staff_shift_rate"])


def reverse_copy(apps, schema_editor):
    SystemSettings = apps.get_model("admin_panel", "SystemSettings")
    for row in SystemSettings.objects.all():
        if row.staff_shift_rate is not None:
            row.shift_rate = row.staff_shift_rate
            row.save(update_fields=["shift_rate"])


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0006_cashsession_review_comment_cashsession_reviewed_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="staff_shift_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("100000"),
                help_text="Staff per-shift rate in UZS (used when salary mode = Shift-based).",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="gm_bonus_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text=(
                    "General Manager bonus as a percentage of the director's "
                    "full salary. Applied on top of the Director payout when "
                    "`Director.is_general_manager=True`. Default 0 (= no bonus)."
                ),
                max_digits=5,
            ),
        ),
        migrations.AlterField(
            model_name="systemsettings",
            name="shift_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("100000"),
                help_text=(
                    "DEPRECATED — kept for one-release backward compatibility. "
                    "Use `staff_shift_rate` instead. (Was originally the staff "
                    "per-shift rate.)"
                ),
                max_digits=12,
            ),
        ),
        migrations.RunPython(
            copy_shift_rate_to_staff_shift_rate, reverse_copy,
        ),
    ]
