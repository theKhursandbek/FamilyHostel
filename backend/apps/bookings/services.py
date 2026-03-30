"""
Booking business logic (README Section 4).

Rules:
    - check_in_date < check_out_date  (also enforced by DB constraint)
    - No overlapping bookings for the same room
    - Discount max 50,000 UZS  (also enforced by model validator)
    - final_price = price_at_booking - discount_amount
    - Status lifecycle: pending -> paid -> completed | pending -> canceled
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.bookings.models import Booking
from apps.branches.models import Room
from apps.reports.services import log_action, notify_roles

__all__ = [
    "create_booking",
    "cancel_booking",
    "complete_booking",
]


# ==============================================================================
# VALIDATION HELPERS
# ==============================================================================


def _validate_dates(check_in_date, check_out_date) -> None:
    """Ensure check-out is strictly after check-in."""
    if check_out_date <= check_in_date:
        raise ValidationError(
            {"check_out_date": "Check-out date must be after check-in date."}
        )


def _validate_no_overlap(room, check_in_date, check_out_date, exclude_pk=None) -> None:
    """
    Ensure no existing active booking overlaps the requested dates.

    Two bookings overlap when:
        existing.check_in  < new.check_out
        AND existing.check_out > new.check_in
    """
    qs = Booking.objects.filter(
        room=room,
        status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
    ).filter(
        Q(check_in_date__lt=check_out_date) & Q(check_out_date__gt=check_in_date),
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    if qs.exists():
        raise ValidationError(
            {"room": "This room already has an overlapping booking for the selected dates."}
        )


def _compute_final_price(price_at_booking: Decimal, discount_amount: Decimal) -> Decimal:
    """Compute and validate final price."""
    final = price_at_booking - discount_amount
    if final < 0:
        raise ValidationError(
            {"discount_amount": "Discount cannot exceed the booking price."}
        )
    return final


# ==============================================================================
# PUBLIC API
# ==============================================================================


@transaction.atomic
def create_booking(
    *,
    client,
    room,
    branch,
    check_in_date,
    check_out_date,
    price_at_booking: Decimal,
    discount_amount: Decimal = Decimal("0"),
    performed_by=None,
) -> Booking:
    """
    Create a new booking with full validation.

    Steps:
        1. Validate dates
        2. Check for overlapping bookings
        3. Compute final_price
        4. Create Booking record (status = pending)
        5. Mark room as booked
        6. Audit log + notify admins/directors

    Returns:
        The created ``Booking`` instance.

    Raises:
        ``ValidationError`` on any rule violation.
    """
    _validate_dates(check_in_date, check_out_date)
    _validate_no_overlap(room, check_in_date, check_out_date)
    final_price = _compute_final_price(price_at_booking, discount_amount)

    booking = Booking.objects.create(
        client=client,
        room=room,
        branch=branch,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        price_at_booking=price_at_booking,
        discount_amount=discount_amount,
        final_price=final_price,
        status=Booking.BookingStatus.PENDING,
    )

    # Mark room as booked
    Room.objects.filter(pk=room.pk).update(status=Room.RoomStatus.BOOKED)

    # --- Audit + Notification ---
    log_action(
        account=performed_by,
        action="booking.created",
        entity_type="Booking",
        entity_id=booking.pk,
        after_data=_booking_snapshot(booking),
    )
    notify_roles(
        roles=["administrator", "director"],
        branch=branch,
        notification_type="booking",
        message=f"New booking #{booking.pk} created for room {room} "
                f"({check_in_date} → {check_out_date}).",
    )

    return booking


@transaction.atomic
def cancel_booking(booking: Booking, *, performed_by=None) -> Booking:
    """
    Cancel a pending booking.

    Only ``pending`` bookings may be canceled (README Section 19).
    Releases the room back to available.
    """
    if booking.status != Booking.BookingStatus.PENDING:
        raise ValidationError(
            {"status": f"Cannot cancel a booking with status '{booking.status}'."}
        )

    before = _booking_snapshot(booking)

    booking.status = Booking.BookingStatus.CANCELED
    booking.save(update_fields=["status", "updated_at"])

    Room.objects.filter(pk=booking.room_id).update(status=Room.RoomStatus.AVAILABLE)

    # --- Audit ---
    log_action(
        account=performed_by,
        action="booking.canceled",
        entity_type="Booking",
        entity_id=booking.pk,
        before_data=before,
        after_data=_booking_snapshot(booking),
    )

    return booking


@transaction.atomic
def complete_booking(booking: Booking, *, performed_by=None) -> Booking:
    """
    Mark a paid booking as completed (guest checked out).

    Triggers room status change to ``cleaning``.
    Cleaning task creation is handled by ``cleaning.services``.
    """
    if booking.status != Booking.BookingStatus.PAID:
        raise ValidationError(
            {"status": "Only paid bookings can be completed."}
        )

    before = _booking_snapshot(booking)

    booking.status = "completed"
    booking.save(update_fields=["status", "updated_at"])

    # Room enters cleaning cycle
    Room.objects.filter(pk=booking.room_id).update(status=Room.RoomStatus.CLEANING)

    # Trigger cleaning task creation (import here to avoid circular imports)
    from apps.cleaning.services import create_cleaning_task

    create_cleaning_task(room=booking.room, branch=booking.branch)

    # --- Audit ---
    log_action(
        account=performed_by,
        action="booking.completed",
        entity_type="Booking",
        entity_id=booking.pk,
        before_data=before,
        after_data=_booking_snapshot(booking),
    )

    return booking


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _booking_snapshot(booking: Booking) -> dict:
    """Return a JSON-serialisable dict of booking state."""
    return {
        "id": booking.pk,
        "status": booking.status,
        "client_id": booking.client_id,
        "room_id": booking.room_id,
        "branch_id": booking.branch_id,
        "check_in_date": str(booking.check_in_date),
        "check_out_date": str(booking.check_out_date),
        "final_price": str(booking.final_price),
    }
