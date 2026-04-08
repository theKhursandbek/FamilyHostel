"""
Facility log management service (Step 21.7).

Business rules:
    - Director+ can create / update facility logs.
    - All actions are audit-logged.
"""

from __future__ import annotations

from django.db import transaction

from apps.reports.models import FacilityLog
from apps.reports.services import log_action

__all__ = [
    "create_facility_log",
    "update_facility_log",
]


@transaction.atomic
def create_facility_log(
    *,
    branch,
    facility_type: str,
    description: str,
    cost=None,
    performed_by=None,
) -> FacilityLog:
    """
    Create a new facility log entry.

    Args:
        branch: The Branch where the issue occurred.
        facility_type: One of ``FacilityLog.FacilityType`` values.
        description: Description of the issue.
        cost: Optional cost associated with the issue.
        performed_by: Account for audit logging.
    """
    kwargs: dict = {
        "branch": branch,
        "type": facility_type,
        "description": description,
    }
    if cost is not None:
        kwargs["cost"] = cost

    log_entry = FacilityLog.objects.create(**kwargs)

    log_action(
        account=performed_by,
        action="facility_log.created",
        entity_type="FacilityLog",
        entity_id=log_entry.pk,
        after_data=_facility_snapshot(log_entry),
    )

    return log_entry


@transaction.atomic
def update_facility_log(
    *, facility_log: FacilityLog, performed_by=None, **kwargs,
) -> FacilityLog:
    """
    Update allowed fields on a facility log.

    Allowed fields: ``type``, ``description``, ``cost``, ``status``.
    """
    before = _facility_snapshot(facility_log)

    allowed = {"type", "description", "cost", "status"}
    update_fields = ["updated_at"]
    for key, value in kwargs.items():
        if key in allowed and value is not None:
            setattr(facility_log, key, value)
            update_fields.append(key)

    facility_log.save(update_fields=update_fields)

    log_action(
        account=performed_by,
        action="facility_log.updated",
        entity_type="FacilityLog",
        entity_id=facility_log.pk,
        before_data=before,
        after_data=_facility_snapshot(facility_log),
    )

    return facility_log


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _facility_snapshot(log: FacilityLog) -> dict:
    """Return a JSON-serialisable dict of facility log state."""
    return {
        "id": log.pk,
        "branch_id": log.branch_id,  # type: ignore[attr-defined]
        "type": log.type,
        "description": log.description,
        "cost": str(log.cost),
        "status": log.status,
    }
