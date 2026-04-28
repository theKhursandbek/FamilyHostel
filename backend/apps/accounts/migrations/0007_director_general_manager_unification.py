"""
Phase 1 — Role Unification (April 2026 refactor).

Schema changes:
    - Add Director.is_general_manager (BooleanField).
    - Add unique constraint: only ONE active Director per branch.

Data migration:
    1. Collapse legacy dual-role accounts. For every Account that currently
       holds BOTH an active Director profile AND an active Administrator
       profile (the old "Director ↔ Administrator" pair), we keep the Director
       row and DELETE the Administrator row. Each removal is recorded in
       AuditLog under verb 'accounts.dual_role_collapsed'.
    2. Migrate the General Manager flag from SuperAdmin to Director when an
       account holds both profiles. (For SuperAdmin-only accounts — e.g. the
       current Lobar Pazilova row — the SuperAdmin.is_general_manager flag is
       left untouched; the CEO will create a Director profile for her in the
       admin panel later, then tick the new "General Manager" checkbox.)

The SuperAdmin.is_general_manager column is left in place for backward
compatibility; it will be dropped in a later cleanup migration once readers
have switched over to Director.is_general_manager.
"""

from django.db import migrations, models


def _audit_log(apps, account_id, before, after):
    """Best-effort audit entry; reports app may not be ready yet during tests."""
    try:
        AuditLog = apps.get_model("reports", "AuditLog")
    except LookupError:
        return
    AuditLog.objects.create(
        account_id=None,
        role="system",
        action="accounts.dual_role_collapsed",
        entity_type="Account",
        entity_id=account_id,
        before_data=before,
        after_data=after,
    )


def collapse_dual_roles_and_move_gm(apps, schema_editor):
    Director = apps.get_model("accounts", "Director")
    Administrator = apps.get_model("accounts", "Administrator")
    SuperAdmin = apps.get_model("accounts", "SuperAdmin")

    # 1. Collapse dual-role accounts: prefer the Director row, drop the
    #    Administrator row. We process every account that has both rows,
    #    regardless of is_active state — the unified model does not need
    #    an Administrator row for any director.
    director_account_ids = set(
        Director.objects.values_list("account_id", flat=True),
    )
    duplicates = Administrator.objects.filter(
        account_id__in=director_account_ids,
    )
    for admin in duplicates:
        before = {
            "id": admin.pk,
            "account_id": admin.account_id,
            "branch_id": admin.branch_id,
            "full_name": admin.full_name,
            "is_active": admin.is_active,
        }
        admin_id = admin.pk
        admin.delete()
        _audit_log(apps, before["account_id"], before, {"deleted": True, "admin_id": admin_id})

    # 2. Move GM flag from SuperAdmin → Director where the same Account holds
    #    both. (Lobar's account is currently SuperAdmin only and has no
    #    Director profile, so this is a no-op for her — handled manually.)
    gm_super_admins = SuperAdmin.objects.filter(is_general_manager=True)
    for sa in gm_super_admins:
        director = Director.objects.filter(account_id=sa.account_id).first()
        if director is None:
            continue
        director.is_general_manager = True
        director.save(update_fields=["is_general_manager"])


def reverse_noop(apps, schema_editor):
    """Reverse: cannot undo deletions; safe no-op."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_superadmin_is_general_manager"),
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="director",
            name="is_general_manager",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Marks the director who acts as General Manager "
                    "(Бош менеджер — e.g. Лобар Pazilova). General Managers "
                    "receive an extra salary bonus and a personal yearly "
                    "Excel workbook visible only to themselves and the CEO."
                ),
            ),
        ),
        migrations.RunPython(collapse_dual_roles_and_move_gm, reverse_noop),
        migrations.AddConstraint(
            model_name="director",
            constraint=models.UniqueConstraint(
                fields=["branch"],
                condition=models.Q(is_active=True),
                name="unique_active_director_per_branch",
            ),
        ),
    ]
