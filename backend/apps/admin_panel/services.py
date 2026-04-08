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
from apps.reports.services import log_action

__all__ = [
    "create_room_inspection",
    "open_cash_session",
    "close_cash_session",
    "handover_cash_session",
]


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


@transaction.atomic
def close_cash_session(
    *,
    session: CashSession,
    closing_balance: Decimal,
    note: str = "",
) -> CashSession:
    """
    Close an active cash session.

    Raises ``ValidationError`` if the session is already closed.
    """
    if session.end_time is not None:
        raise ValidationError(
            {"session": "This cash session is already closed."},
        )

    before = _session_snapshot(session)

    session.end_time = timezone.now()
    session.closing_balance = closing_balance
    session.difference = closing_balance - session.opening_balance
    if note:
        session.note = note
    session.save(
        update_fields=[
            "end_time", "closing_balance", "difference", "note", "updated_at",
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

    Steps:
        1. Close the current session with the provided closing balance.
        2. Record ``handed_over_to``.

    Raises ``ValidationError`` if:
        - Session is already closed.
        - ``handed_over_to`` is the same admin as the session owner.
    """
    if session.end_time is not None:
        raise ValidationError(
            {"session": "This cash session is already closed."},
        )

    if session.admin_id == handed_over_to.pk:  # type: ignore[union-attr]
        raise ValidationError(
            {"handed_over_to": "Cannot hand over to the same admin."},
        )

    before = _session_snapshot(session)

    session.end_time = timezone.now()
    session.closing_balance = closing_balance
    session.difference = closing_balance - session.opening_balance
    session.handed_over_to = handed_over_to
    if note:
        session.note = note
    session.save(
        update_fields=[
            "end_time", "closing_balance", "difference",
            "handed_over_to", "note", "updated_at",
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
        "difference": str(session.difference) if session.difference else None,
        "handed_over_to_id": session.handed_over_to_id,  # type: ignore[attr-defined]
        "note": session.note,
    }
