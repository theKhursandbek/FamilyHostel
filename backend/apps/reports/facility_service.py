"""
Facility expense workflow service (REFACTOR_PLAN_2026_04 \u00a77.3).

Lifecycle::

    request_expense  -> pending
    approve_expense  -> approved_cash | approved_card
    reject_expense   -> rejected
    mark_paid        -> paid
    mark_resolved    -> resolved

Every step writes an audit-log entry via :func:`log_action` and notifies
the relevant role via :func:`notify_roles`.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.reports.models import FacilityLog
from apps.reports.services import log_action, notify_roles

__all__ = [
    "create_facility_log",
    "update_facility_log",
    "request_expense",
    "approve_expense",
    "reject_expense",
    "mark_paid",
    "mark_resolved",
]


# ==============================================================================
# LEGACY (kept so old call sites + tests keep working)
# ==============================================================================


@transaction.atomic
def create_facility_log(
    *,
    branch,
    facility_type: str,
    description: str,
    cost=None,
    shift_type: str | None = None,
    performed_by=None,
) -> FacilityLog:
    """Legacy alias for :func:`request_expense` (kept for backwards compat)."""
    return request_expense(
        branch=branch,
        director=performed_by,
        facility_type=facility_type,
        description=description,
        cost=cost,
        shift_type=shift_type,
    )


@transaction.atomic
def update_facility_log(
    *, facility_log: FacilityLog, performed_by=None, **kwargs,
) -> FacilityLog:
    """Update editable fields on a facility log.

    Allowed: ``type``, ``shift_type``, ``description``, ``cost``, ``status``.
    Status hand-offs should normally go through dedicated approve/reject/
    mark-paid helpers; raw status writes are kept here for backwards compat.
    """
    before = _snapshot(facility_log)

    allowed = {"type", "shift_type", "description", "cost", "status"}
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
        after_data=_snapshot(facility_log),
    )
    return facility_log


# ==============================================================================
# REQUEST
# ==============================================================================


@transaction.atomic
def request_expense(
    *,
    branch,
    director,
    facility_type: str,
    description: str,
    cost=None,
    shift_type: str | None = None,
) -> FacilityLog:
    """Director files a new expense request (status=pending)."""
    log_entry = FacilityLog.objects.create(
        branch=branch,
        requested_by=director,
        type=facility_type,
        description=description,
        cost=cost or Decimal("0"),
        shift_type=shift_type or None,
        status=FacilityLog.LogStatus.PENDING,
    )

    log_action(
        account=director,
        action="facility_log.requested",
        entity_type="FacilityLog",
        entity_id=log_entry.pk,
        after_data=_snapshot(log_entry),
    )
    notify_roles(
        roles=["superadmin"],
        branch=branch,
        notification_type="expense_request",
        message=(
            f"New expense request from {branch.name}: "
            f"{log_entry.get_type_display()} \u2014 {log_entry.cost} \u0441\u0443\u043c"
        ),
    )
    return log_entry


# ==============================================================================
# APPROVE / REJECT
# ==============================================================================


def _month_to_date_approved(branch, *, when=None) -> Decimal:
    """Sum approved/paid/resolved expenses for the calendar month of ``when``."""
    when = when or timezone.now()
    start = when.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    qs = FacilityLog.objects.filter(
        branch=branch,
        approved_at__gte=start,
        approved_at__lte=when,
        status__in=[
            FacilityLog.LogStatus.APPROVED_CASH,
            FacilityLog.LogStatus.APPROVED_CARD,
            FacilityLog.LogStatus.PAID,
            FacilityLog.LogStatus.RESOLVED,
        ],
    )
    return qs.aggregate(total=Sum("cost"))["total"] or Decimal("0")


@transaction.atomic
def approve_expense(
    *,
    request_obj: FacilityLog,
    ceo,
    payment_method: str,
    note: str = "",
    over_limit_justified: bool = False,
    over_limit_reason: str = "",
) -> FacilityLog:
    """CEO approves a pending request, choosing cash or card payment."""
    if request_obj.status != FacilityLog.LogStatus.PENDING:
        raise ValidationError(
            f"Only pending requests can be approved (current: {request_obj.status}).",
        )
    if payment_method not in {
        FacilityLog.PaymentMethod.CASH,
        FacilityLog.PaymentMethod.CARD,
    }:
        raise ValidationError({"payment_method": "Must be 'cash' or 'card'."})

    branch = request_obj.branch
    limit = Decimal(branch.monthly_expense_limit or 0)
    if limit > 0:
        mtd = _month_to_date_approved(branch)
        candidate = mtd + Decimal(request_obj.cost or 0)
        if candidate > limit and not over_limit_justified:
            raise ValidationError(
                {
                    "over_limit_justified": (
                        f"Approving this request would push month-to-date "
                        f"approved expenses to {candidate} \u0441\u0443\u043c, "
                        f"above the {limit} \u0441\u0443\u043c monthly limit. "
                        f"Set over_limit_justified=True with an over_limit_reason "
                        f"to override."
                    ),
                },
            )
        if over_limit_justified and not over_limit_reason.strip():
            raise ValidationError(
                {"over_limit_reason": "Justification text is required."},
            )

    before = _snapshot(request_obj)
    request_obj.status = (
        FacilityLog.LogStatus.APPROVED_CASH
        if payment_method == FacilityLog.PaymentMethod.CASH
        else FacilityLog.LogStatus.APPROVED_CARD
    )
    request_obj.payment_method = payment_method
    request_obj.approved_by = getattr(ceo, "superadmin_profile", None) or _superadmin_for(ceo)
    request_obj.approved_at = timezone.now()
    request_obj.approval_note = note or ""
    request_obj.over_limit_justified = bool(over_limit_justified)
    request_obj.over_limit_reason = over_limit_reason or ""
    request_obj.save(update_fields=[
        "status", "payment_method", "approved_by", "approved_at",
        "approval_note", "over_limit_justified", "over_limit_reason",
        "updated_at",
    ])

    log_action(
        account=ceo,
        action="facility_log.approved",
        entity_type="FacilityLog",
        entity_id=request_obj.pk,
        before_data=before,
        after_data=_snapshot(request_obj),
    )
    notify_roles(
        roles=["director"],
        branch=branch,
        notification_type="expense_approved",
        message=(
            f"Expense approved ({payment_method}): "
            f"{request_obj.get_type_display()} \u2014 {request_obj.cost} \u0441\u0443\u043c"
        ),
    )
    return request_obj


@transaction.atomic
def reject_expense(*, request_obj: FacilityLog, ceo, reason: str) -> FacilityLog:
    """CEO rejects a pending request."""
    if request_obj.status != FacilityLog.LogStatus.PENDING:
        raise ValidationError("Only pending requests can be rejected.")
    if not (reason or "").strip():
        raise ValidationError({"reason": "A rejection reason is required."})

    before = _snapshot(request_obj)
    request_obj.status = FacilityLog.LogStatus.REJECTED
    request_obj.rejected_by = getattr(ceo, "superadmin_profile", None) or _superadmin_for(ceo)
    request_obj.rejected_at = timezone.now()
    request_obj.rejection_reason = reason
    request_obj.save(update_fields=[
        "status", "rejected_by", "rejected_at", "rejection_reason", "updated_at",
    ])

    log_action(
        account=ceo,
        action="facility_log.rejected",
        entity_type="FacilityLog",
        entity_id=request_obj.pk,
        before_data=before,
        after_data=_snapshot(request_obj),
    )
    notify_roles(
        roles=["director"],
        branch=request_obj.branch,
        notification_type="expense_rejected",
        message=(
            f"Expense rejected: {request_obj.get_type_display()} "
            f"\u2014 {reason}"
        ),
    )
    return request_obj


# ==============================================================================
# PAID / RESOLVED
# ==============================================================================


@transaction.atomic
def mark_paid(*, request_obj: FacilityLog, actor) -> FacilityLog:
    """Cash: director taps after taking cash. Card: CEO after bank transfer."""
    if request_obj.status not in {
        FacilityLog.LogStatus.APPROVED_CASH,
        FacilityLog.LogStatus.APPROVED_CARD,
    }:
        raise ValidationError(
            "Only approved requests can be marked paid (current: "
            f"{request_obj.status}).",
        )
    before = _snapshot(request_obj)
    request_obj.status = FacilityLog.LogStatus.PAID
    request_obj.paid_at = timezone.now()
    request_obj.save(update_fields=["status", "paid_at", "updated_at"])

    log_action(
        account=actor,
        action="facility_log.paid",
        entity_type="FacilityLog",
        entity_id=request_obj.pk,
        before_data=before,
        after_data=_snapshot(request_obj),
    )
    return request_obj


@transaction.atomic
def mark_resolved(*, request_obj: FacilityLog, actor) -> FacilityLog:
    """Final close-out (e.g. repair finished, receipt filed)."""
    if request_obj.status != FacilityLog.LogStatus.PAID:
        raise ValidationError("Only paid requests can be resolved.")
    before = _snapshot(request_obj)
    request_obj.status = FacilityLog.LogStatus.RESOLVED
    request_obj.resolved_at = timezone.now()
    request_obj.save(update_fields=["status", "resolved_at", "updated_at"])

    log_action(
        account=actor,
        action="facility_log.resolved",
        entity_type="FacilityLog",
        entity_id=request_obj.pk,
        before_data=before,
        after_data=_snapshot(request_obj),
    )
    return request_obj


# ==============================================================================
# HELPERS
# ==============================================================================


def _superadmin_for(account):
    """Return a SuperAdmin profile attached to ``account``, if any."""
    if account is None:
        return None
    from apps.accounts.models import SuperAdmin
    return SuperAdmin.objects.filter(account=account).first()


def _snapshot(log: FacilityLog) -> dict:
    """JSON-safe state snapshot for audit trail."""
    return {
        "id": log.pk,
        "branch_id": log.branch_id,  # type: ignore[attr-defined]
        "type": log.type,
        "shift_type": log.shift_type,
        "description": log.description,
        "cost": str(log.cost),
        "status": log.status,
        "payment_method": log.payment_method,
        "requested_by_id": log.requested_by_id,  # type: ignore[attr-defined]
        "approved_by_id": log.approved_by_id,  # type: ignore[attr-defined]
        "approved_at": log.approved_at.isoformat() if log.approved_at else None,
        "approval_note": log.approval_note,
        "rejected_by_id": log.rejected_by_id,  # type: ignore[attr-defined]
        "rejected_at": log.rejected_at.isoformat() if log.rejected_at else None,
        "rejection_reason": log.rejection_reason,
        "over_limit_justified": log.over_limit_justified,
        "over_limit_reason": log.over_limit_reason,
        "paid_at": log.paid_at.isoformat() if log.paid_at else None,
        "resolved_at": log.resolved_at.isoformat() if log.resolved_at else None,
    }
