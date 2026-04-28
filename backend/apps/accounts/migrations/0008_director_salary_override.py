"""
Phase 2 (REFACTOR_PLAN_2026_04 §1.1 + §5.1).

Adds ``Director.salary_override`` and migrates data from the deprecated
``Director.salary`` column. We copy the value into ``salary_override`` only
when it differs from ``SystemSettings.director_fixed_salary`` — that way
unchanged directors keep tracking the global default automatically.

The deprecated ``Director.salary`` column is left in place; it will be
dropped in the §10 cleanup pass after one full release.
"""

from decimal import Decimal

from django.db import migrations, models


def copy_salary_to_override(apps, schema_editor):
    director_model = apps.get_model("accounts", "Director")
    settings_model = apps.get_model("admin_panel", "SystemSettings")

    settings_obj = settings_model.objects.first()
    default_salary = (
        Decimal(settings_obj.director_fixed_salary)
        if settings_obj is not None
        else Decimal("2000000")
    )

    for director in director_model.objects.all():
        current = Decimal(director.salary or 0)
        # Only persist as override when it actually differs from the global
        # default — otherwise keep it NULL so future SystemSettings changes
        # propagate automatically.
        if current and current != default_salary:
            director.salary_override = current
            director.save(update_fields=["salary_override"])


def noop_reverse(apps, schema_editor):
    """Forward-only data move; reverse is a no-op (data stays in salary)."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_director_general_manager_unification"),
        ("admin_panel", "0006_cashsession_review_comment_cashsession_reviewed_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="director",
            name="salary_override",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Per-person fixed monthly salary override in UZS. If null, "
                    "`SystemSettings.director_fixed_salary` is used."
                ),
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="director",
            name="salary",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("2000000"),
                help_text=(
                    "DEPRECATED — kept for backward compatibility through the "
                    "2026-04 refactor cleanup pass. Read from `salary_override` "
                    "instead, falling back to `SystemSettings.director_fixed_salary`."
                ),
                max_digits=12,
            ),
        ),
        migrations.RunPython(copy_salary_to_override, noop_reverse),
    ]
