"""
Penalty management service (Step 21.7).

Business rules:
    - Only Director+ can create / update / delete penalties.
    - All actions are audit-logged.
"""

from __future__ import annotations

from django.db import transaction

from apps.reports.models import Penalty
from apps.reports.services import log_action

__all__ = [
    "create_penalty",
    "update_penalty",
    "delete_penalty",
]


@transaction.atomic
def create_penalty(
    *,
    account,
    penalty_type: str,
    count: int = 1,
    penalty_amount,
    reason: str = "",
    created_by=None,
    performed_by=None,
) -> Penalty:
    """
    Create a new penalty record.

    Args:
        account: The Account being penalised.
        penalty_type: One of ``Penalty.PenaltyType`` values.
        count: Number of infractions.
        penalty_amount: Monetary penalty.
        reason: Free-text reason.
        created_by: The Account that created the penalty (director/superadmin).
        performed_by: Account for audit logging (same as created_by usually).
    """
    penalty = Penalty.objects.create(
        account=account,
        type=penalty_type,
        count=count,
        penalty_amount=penalty_amount,
        reason=reason,
        created_by=created_by,
    )

    log_action(
        account=performed_by or created_by,
        action="penalty.created",
        entity_type="Penalty",
        entity_id=penalty.pk,
        after_data=_penalty_snapshot(penalty),
    )

    return penalty


@transaction.atomic
def update_penalty(*, penalty: Penalty, performed_by=None, **kwargs) -> Penalty:
    """
    Update allowed fields on a penalty.

    Allowed fields: ``type``, ``count``, ``penalty_amount``, ``reason``.
    """
    before = _penalty_snapshot(penalty)

    allowed = {"type", "count", "penalty_amount", "reason"}
    update_fields = ["updated_at"]
    for key, value in kwargs.items():
        if key not in allowed:
            continue
        # ``type`` is nullable on the model — allow explicit None so callers
        # can clear an existing category. For all other fields, ``None`` means
        # "field not sent" (per CreatePenaltySerializer / UpdatePenalty rules).
        if key != "type" and value is None:
            continue
        setattr(penalty, key, value)
        update_fields.append(key)

    penalty.save(update_fields=update_fields)

    log_action(
        account=performed_by,
        action="penalty.updated",
        entity_type="Penalty",
        entity_id=penalty.pk,
        before_data=before,
        after_data=_penalty_snapshot(penalty),
    )

    return penalty


@transaction.atomic
def delete_penalty(*, penalty: Penalty, performed_by=None) -> None:
    """Delete a penalty record."""
    before = _penalty_snapshot(penalty)
    penalty_id = penalty.pk
    penalty.delete()

    log_action(
        account=performed_by,
        action="penalty.deleted",
        entity_type="Penalty",
        entity_id=penalty_id,
        before_data=before,
    )


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _penalty_snapshot(p: Penalty) -> dict:
    """Return a JSON-serialisable dict of penalty state."""
    return {
        "id": p.pk,
        "account_id": p.account_id,  # type: ignore[attr-defined]
        "type": p.type,
        "count": p.count,
        "penalty_amount": str(p.penalty_amount),
        "reason": p.reason,
        "created_by_id": p.created_by_id,  # type: ignore[attr-defined]
    }
