"""
Day-Off Request business logic (Step 21.5).

Rules:
    - Staff / Admin can create a day-off request for themselves.
    - Date range must be valid (end >= start, start >= today).
    - Overlapping *pending* or *approved* requests are rejected.
    - Director (or SuperAdmin) can approve / reject.
    - Approve / reject actions are audit-logged.
"""

from __future__ import annotations

import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.reports.services import log_action
from apps.staff.models import DayOffRequest

__all__ = [
    "create_day_off_request",
    "approve_day_off_request",
    "reject_day_off_request",
]


# ==============================================================================
# CREATE
# ==============================================================================


@transaction.atomic
def create_day_off_request(
    *,
    account,
    branch,
    start_date: datetime.date,
    end_date: datetime.date,
    reason: str = "",
) -> DayOffRequest:
    """
    Create a new day-off request.

    Raises ``ValidationError`` when:
        - end_date < start_date
        - start_date is in the past
        - An overlapping pending/approved request already exists
    """
    today = datetime.date.today()

    if end_date < start_date:
        raise ValidationError(
            {"end_date": "End date cannot be before start date."},
        )

    if start_date < today:
        raise ValidationError(
            {"start_date": "Start date cannot be in the past."},
        )

    # Check for overlapping requests (pending or approved)
    overlap = DayOffRequest.objects.filter(
        account=account,
        status__in=[DayOffRequest.Status.PENDING, DayOffRequest.Status.APPROVED],
    ).filter(
        # Overlap condition: existing.start <= new.end AND existing.end >= new.start
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()

    if overlap:
        raise ValidationError(
            {"start_date": "You already have a pending or approved request overlapping these dates."},
        )

    request_obj = DayOffRequest.objects.create(
        account=account,
        branch=branch,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=DayOffRequest.Status.PENDING,
    )

    # --- Audit ---
    log_action(
        account=account,
        action="day_off_request.created",
        entity_type="DayOffRequest",
        entity_id=request_obj.pk,
        after_data=_day_off_snapshot(request_obj),
    )

    return request_obj


# ==============================================================================
# APPROVE
# ==============================================================================


@transaction.atomic
def approve_day_off_request(
    *,
    day_off_request: DayOffRequest,
    reviewed_by,
    comment: str = "",
) -> DayOffRequest:
    """
    Approve a pending day-off request.

    Raises ``ValidationError`` if the request is not pending.
    """
    if day_off_request.status != DayOffRequest.Status.PENDING:
        raise ValidationError(
            {"status": "Only pending requests can be approved."},
        )

    before = _day_off_snapshot(day_off_request)

    day_off_request.status = DayOffRequest.Status.APPROVED
    day_off_request.reviewed_by = reviewed_by
    day_off_request.reviewed_at = timezone.now()
    day_off_request.review_comment = comment
    day_off_request.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"],
    )

    # --- Audit ---
    reviewer_account = (
        reviewed_by.account if hasattr(reviewed_by, "account") else None
    )
    log_action(
        account=reviewer_account,
        action="day_off_request.approved",
        entity_type="DayOffRequest",
        entity_id=day_off_request.pk,
        before_data=before,
        after_data=_day_off_snapshot(day_off_request),
    )

    return day_off_request


# ==============================================================================
# REJECT
# ==============================================================================


@transaction.atomic
def reject_day_off_request(
    *,
    day_off_request: DayOffRequest,
    reviewed_by,
    comment: str = "",
) -> DayOffRequest:
    """
    Reject a pending day-off request.

    Raises ``ValidationError`` if the request is not pending.
    """
    if day_off_request.status != DayOffRequest.Status.PENDING:
        raise ValidationError(
            {"status": "Only pending requests can be rejected."},
        )

    before = _day_off_snapshot(day_off_request)

    day_off_request.status = DayOffRequest.Status.REJECTED
    day_off_request.reviewed_by = reviewed_by
    day_off_request.reviewed_at = timezone.now()
    day_off_request.review_comment = comment
    day_off_request.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"],
    )

    # --- Audit ---
    reviewer_account = (
        reviewed_by.account if hasattr(reviewed_by, "account") else None
    )
    log_action(
        account=reviewer_account,
        action="day_off_request.rejected",
        entity_type="DayOffRequest",
        entity_id=day_off_request.pk,
        before_data=before,
        after_data=_day_off_snapshot(day_off_request),
    )

    return day_off_request


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _day_off_snapshot(req: DayOffRequest) -> dict:
    """Return a JSON-serialisable dict of day-off request state."""
    return {
        "id": req.pk,
        "account_id": req.account_id,  # type: ignore[attr-defined]
        "branch_id": req.branch_id,  # type: ignore[attr-defined]
        "start_date": str(req.start_date),
        "end_date": str(req.end_date),
        "reason": req.reason,
        "status": req.status,
        "reviewed_by_id": req.reviewed_by_id,  # type: ignore[attr-defined]
        "reviewed_at": str(req.reviewed_at) if req.reviewed_at else None,
        "review_comment": req.review_comment,
    }
