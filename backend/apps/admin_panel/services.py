"""
Admin Panel service layer — Room Inspections & Cash Sessions (Step 21.6).

Business rules:
    Room Inspections:
        - Admin performs after checkout
        - Linked to booking if applicable
    Cash Sessions:
        - One active session per admin at a time
        - Only current admin can close or hand over
        - Handover transfers to next admin, closes current session
    All actions are audit-logged.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.admin_panel.models import CashSession, RoomInspection
from apps.reports.services import log_action, notify_roles

__all__ = [
    "create_room_inspection",
    "open_cash_session",
    "close_cash_session",
    "handover_cash_session",
    "review_cash_session",
    "previous_close_for_branch",
    "compute_session_flows",
    "VARIANCE_NOTE_THRESHOLD",
]


# ==============================================================================
# CASH POLICY CONSTANTS
# ==============================================================================

# If |variance| exceeds this amount (UZS), the closing/handover request
# *must* include a non-empty note explaining the discrepancy.
VARIANCE_NOTE_THRESHOLD = Decimal("5000")


# ==============================================================================
# ROOM INSPECTION
# ==============================================================================


@transaction.atomic
def create_room_inspection(
    *,
    room,
    branch,
    inspected_by,
    status: str,
    notes: str = "",
    booking=None,
) -> RoomInspection:
    """
    Create a new room inspection record.

    Args:
        room: The Room being inspected.
        branch: Branch the room belongs to.
        inspected_by: Administrator performing the inspection.
        status: One of ``RoomInspection.InspectionStatus`` values.
        notes: Free-text notes.
        booking: Optional linked Booking.
    """
    inspection = RoomInspection.objects.create(
        room=room,
        branch=branch,
        inspected_by=inspected_by,
        booking=booking,
        status=status,
        notes=notes,
    )

    # Determine the account for audit logging
    admin_account = (
        inspected_by.account if hasattr(inspected_by, "account") else None
    )

    log_action(
        account=admin_account,
        action="room_inspection.created",
        entity_type="RoomInspection",
        entity_id=inspection.pk,
        after_data=_inspection_snapshot(inspection),
    )

    return inspection


# ==============================================================================
# CASH SESSION — OPEN
# ==============================================================================


@transaction.atomic
def open_cash_session(
    *,
    admin,
    branch,
    shift_type: str,
    opening_balance: Decimal,
    note: str = "",
) -> CashSession:
    """
    Open a new cash session.

    Raises ``ValidationError`` if the admin already has an active
    (unclosed) session.
    """
    active = CashSession.objects.filter(
        admin=admin,
        end_time__isnull=True,
    ).exists()

    if active:
        raise ValidationError(
            {"admin": "This admin already has an active cash session."},
        )

    session = CashSession.objects.create(
        admin=admin,
        branch=branch,
        shift_type=shift_type,
        start_time=timezone.now(),
        opening_balance=opening_balance,
        note=note,
    )

    admin_account = admin.account if hasattr(admin, "account") else None
    log_action(
        account=admin_account,
        action="cash_session.opened",
        entity_type="CashSession",
        entity_id=session.pk,
        after_data=_session_snapshot(session),
    )

    return session


# ==============================================================================
# CASH SESSION — CLOSE
# ==============================================================================


def compute_session_flows(session: CashSession, *, until=None) -> tuple[Decimal, Decimal]:
    """Return ``(cash_in, cash_out)`` for ``session`` between open and ``until``.

    Mirrors the math used by ``CashSessionSerializer._flows`` so the service
    layer and the API expose the same numbers.

    cash_in   — Cash payments collected for bookings of this branch.
    cash_out  — Facility-log expenses for this branch (matching shift_type
                or with no shift_type assigned).
    """
    from django.db.models import Q, Sum

    from apps.payments.models import Payment
    from apps.reports.models import FacilityLog

    end = until or session.end_time or timezone.now()

    cash_in = (
        Payment.objects.filter(
            booking__branch_id=session.branch_id,  # type: ignore[attr-defined]
            method=Payment.PaymentMethod.CASH,
            is_paid=True,
            paid_at__gte=session.start_time,
            paid_at__lte=end,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    cash_out = (
        FacilityLog.objects.filter(
            branch_id=session.branch_id,  # type: ignore[attr-defined]
            status=FacilityLog.LogStatus.PAID,
            payment_method=FacilityLog.PaymentMethod.CASH,
            paid_at__gte=session.start_time,
            paid_at__lte=end,
        )
        .filter(
            Q(shift_type=session.shift_type)
            | Q(shift_type__isnull=True)
            | Q(shift_type="")
        )
        .aggregate(total=Sum("cost"))["total"]
        or Decimal("0")
    )

    return Decimal(cash_in), Decimal(cash_out)


def previous_close_for_branch(branch, shift_type: str | None = None) -> CashSession | None:
    """Return the most recently closed session for ``branch`` (any admin).

    Used to surface a "previous shift closed at X" hint to the next admin
    so they can reconcile the opening balance before starting their shift.
    Optionally filters by ``shift_type``.
    """
    qs = CashSession.objects.filter(
        branch=branch,
        end_time__isnull=False,
    )
    if shift_type:
        qs = qs.filter(shift_type=shift_type)
    return qs.order_by("-end_time").first()


def _finalise_close(
    session: CashSession,
    closing_balance: Decimal,
    note: str,
) -> Decimal:
    """Compute real variance, validate note requirement, return variance.

    Real variance = ``closing_balance - (opening + cash_in - cash_out)``.
    Raises ``ValidationError`` if |variance| exceeds the note threshold
    while the note is empty.
    """
    cash_in, cash_out = compute_session_flows(session, until=timezone.now())
    expected = Decimal(session.opening_balance or 0) + cash_in - cash_out
    variance = Decimal(closing_balance) - expected

    if abs(variance) > VARIANCE_NOTE_THRESHOLD and not note.strip():
        raise ValidationError({
            "note": (
                f"A note is required when the cash variance exceeds "
                f"{VARIANCE_NOTE_THRESHOLD:,.0f} UZS "
                f"(current variance: {variance:,.2f})."
            ),
        })

    return variance


def _notify_director_of_variance(session: CashSession, variance: Decimal, kind: str) -> None:
    """Push a notification to directors of the branch when variance != 0."""
    if variance == 0:
        return
    sign = "surplus" if variance > 0 else "shortage"
    notify_roles(
        roles=["director"],
        branch=session.branch,
        notification_type="cash_session",
        message=(
            f"Cash {kind} #{session.pk}: {sign} of "
            f"{abs(variance):,.2f} UZS by "
            f"{getattr(session.admin, 'full_name', None) or 'admin'} "  # type: ignore[union-attr]
            f"({session.shift_type} shift). Awaiting review."
        ),
    )


@transaction.atomic
def close_cash_session(
    *,
    session: CashSession,
    closing_balance: Decimal,
    note: str = "",
) -> CashSession:
    """
    Close an active cash session.

    Enforces:
        - Session must still be open.
        - If the recomputed variance exceeds ``VARIANCE_NOTE_THRESHOLD``
          a non-empty ``note`` is required.

    Side-effects:
        - ``session.difference`` is the *real* variance
          (closing − (opening + cash_in − cash_out)).
        - ``variance_status`` becomes ``pending`` when variance ≠ 0,
          otherwise ``approved``.
        - Directors of the branch are notified when variance ≠ 0.
    """
    if session.end_time is not None:
        raise ValidationError(
            {"session": "This cash session is already closed."},
        )

    variance = _finalise_close(session, closing_balance, note)

    before = _session_snapshot(session)

    session.end_time = timezone.now()
    session.closing_balance = closing_balance
    session.difference = variance
    session.variance_status = (
        CashSession.VarianceStatus.APPROVED
        if variance == 0
        else CashSession.VarianceStatus.PENDING
    )
    if note:
        session.note = note
    session.save(
        update_fields=[
            "end_time", "closing_balance", "difference",
            "variance_status", "note", "updated_at",
        ],
    )

    admin_account = (
        session.admin.account  # type: ignore[union-attr]
        if hasattr(session.admin, "account")
        else None
    )
    log_action(
        account=admin_account,
        action="cash_session.closed",
        entity_type="CashSession",
        entity_id=session.pk,
        before_data=before,
        after_data=_session_snapshot(session),
    )

    _notify_director_of_variance(session, variance, "close")

    return session


# ==============================================================================
# CASH SESSION — HANDOVER
# ==============================================================================


@transaction.atomic
def handover_cash_session(
    *,
    session: CashSession,
    handed_over_to,
    closing_balance: Decimal,
    note: str = "",
) -> CashSession:
    """
    Hand over a cash session to the next admin.

    Same variance-control rules as ``close_cash_session`` plus:
        - ``handed_over_to`` must differ from the session owner.
    """
    if session.end_time is not None:
        raise ValidationError(
            {"session": "This cash session is already closed."},
        )

    if session.admin_id == handed_over_to.pk:  # type: ignore[union-attr]
        raise ValidationError(
            {"handed_over_to": "Cannot hand over to the same admin."},
        )

    variance = _finalise_close(session, closing_balance, note)

    before = _session_snapshot(session)

    session.end_time = timezone.now()
    session.closing_balance = closing_balance
    session.difference = variance
    session.variance_status = (
        CashSession.VarianceStatus.APPROVED
        if variance == 0
        else CashSession.VarianceStatus.PENDING
    )
    session.handed_over_to = handed_over_to
    if note:
        session.note = note
    session.save(
        update_fields=[
            "end_time", "closing_balance", "difference",
            "variance_status", "handed_over_to", "note", "updated_at",
        ],
    )

    admin_account = (
        session.admin.account  # type: ignore[union-attr]
        if hasattr(session.admin, "account")
        else None
    )
    log_action(
        account=admin_account,
        action="cash_session.handover",
        entity_type="CashSession",
        entity_id=session.pk,
        before_data=before,
        after_data=_session_snapshot(session),
    )

    _notify_director_of_variance(session, variance, "handover")

    return session


# ==============================================================================
# CASH SESSION — DIRECTOR REVIEW
# ==============================================================================


@transaction.atomic
def review_cash_session(
    *,
    session: CashSession,
    director,
    decision: str,
    comment: str = "",
) -> CashSession:
    """Director approves or disputes a closed session's variance.

    Args:
        session:  Closed cash session under review.
        director: Director performing the review.
        decision: ``"approved"`` or ``"disputed"``.
        comment:  Optional free-text comment (required for "disputed").

    Raises:
        ValidationError if the session is still open, the decision is
        unknown, or a dispute is filed without a comment.
    """
    if session.end_time is None:
        raise ValidationError(
            {"session": "Cannot review an open cash session."},
        )

    valid = {
        CashSession.VarianceStatus.APPROVED,
        CashSession.VarianceStatus.DISPUTED,
    }
    if decision not in valid:
        raise ValidationError(
            {"decision": f"Decision must be one of: {', '.join(sorted(valid))}."},
        )

    if decision == CashSession.VarianceStatus.DISPUTED and not comment.strip():
        raise ValidationError(
            {"comment": "A comment is required when disputing a session."},
        )

    before = _session_snapshot(session)

    session.variance_status = decision
    session.reviewed_by = director
    session.reviewed_at = timezone.now()
    session.review_comment = comment
    session.save(
        update_fields=[
            "variance_status", "reviewed_by", "reviewed_at",
            "review_comment", "updated_at",
        ],
    )

    director_account = director.account if hasattr(director, "account") else None
    log_action(
        account=director_account,
        action=f"cash_session.{decision}",
        entity_type="CashSession",
        entity_id=session.pk,
        before_data=before,
        after_data=_session_snapshot(session),
    )

    # Notify the admin who owned the session about the outcome.
    if decision == CashSession.VarianceStatus.DISPUTED:
        notify_roles(
            roles=["administrator"],
            branch=session.branch,
            notification_type="cash_session",
            message=(
                f"Cash session #{session.pk} was disputed by director. "
                f"Comment: {comment[:140]}"
            ),
        )

    return session


# ==============================================================================
# SNAPSHOT HELPERS
# ==============================================================================


def _inspection_snapshot(insp: RoomInspection) -> dict:
    """Return a JSON-serialisable dict of inspection state."""
    return {
        "id": insp.pk,
        "room_id": insp.room_id,  # type: ignore[attr-defined]
        "branch_id": insp.branch_id,  # type: ignore[attr-defined]
        "inspected_by_id": insp.inspected_by_id,  # type: ignore[attr-defined]
        "booking_id": insp.booking_id,  # type: ignore[attr-defined]
        "status": insp.status,
        "notes": insp.notes,
    }


def _session_snapshot(session: CashSession) -> dict:
    """Return a JSON-serialisable dict of cash session state."""
    return {
        "id": session.pk,
        "admin_id": session.admin_id,  # type: ignore[attr-defined]
        "branch_id": session.branch_id,  # type: ignore[attr-defined]
        "shift_type": session.shift_type,
        "start_time": str(session.start_time),
        "end_time": str(session.end_time) if session.end_time else None,
        "opening_balance": str(session.opening_balance),
        "closing_balance": str(session.closing_balance) if session.closing_balance else None,
        "difference": str(session.difference) if session.difference is not None else None,
        "variance_status": session.variance_status,
        "reviewed_by_id": session.reviewed_by_id,  # type: ignore[attr-defined]
        "reviewed_at": str(session.reviewed_at) if session.reviewed_at else None,
        "review_comment": session.review_comment,
        "handed_over_to_id": session.handed_over_to_id,  # type: ignore[attr-defined]
        "note": session.note,
    }
