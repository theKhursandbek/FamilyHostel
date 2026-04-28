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

import time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import Account, Client
from apps.bookings.models import Booking
from apps.branches.models import Room
from apps.reports.services import log_action, notify_roles

__all__ = [
    "create_booking",
    "create_walkin_booking",
    "cancel_booking",
    "complete_booking",
    "extend_booking",
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
def complete_booking(
    booking: Booking,
    *,
    performed_by=None,
    refund_amount=None,  # accepted for backward compat — IGNORED.
) -> Booking:
    """
    Mark a paid booking as completed (guest checked out).

    Per business rule (April 2026): early checkout does NOT trigger a
    refund — the customer forfeits the unused nights. The ``refund_amount``
    parameter is retained only so existing callers don't break; it is
    silently ignored.  Refunds are still possible via the explicit
    ``POST /bookings/{pk}/refund/`` endpoint (manager discretion, audited).

    Triggers room status change to ``cleaning``.
    """
    if booking.status != Booking.BookingStatus.PAID:
        raise ValidationError(
            {"status": "Only paid bookings can be checked out."}
        )

    # Note: ``refund_amount`` intentionally ignored — see docstring.
    _ = refund_amount

    before = _booking_snapshot(booking)

    booking.status = "completed"
    booking.save(update_fields=["status", "updated_at"])

    # Room enters cleaning cycle
    Room.objects.filter(pk=booking.room_id).update(status=Room.RoomStatus.CLEANING)

    # Trigger cleaning task creation (import here to avoid circular imports).
    # If the room already has an active cleaning task (e.g. left over from a
    # previous test cycle, or from another just-completed booking on the same
    # room), reuse it instead of crashing the checkout flow.
    from apps.cleaning.models import CleaningTask
    from apps.cleaning.services import create_cleaning_task

    has_active = CleaningTask.objects.filter(room=booking.room).exclude(
        status=CleaningTask.TaskStatus.COMPLETED,
    ).exists()
    if not has_active:
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


# ==============================================================================
# WALK-IN GUEST CREATION (Account + Client + Booking in one atomic step)
# ==============================================================================


def _next_synthetic_telegram_id() -> int:
    """
    Generate a unique negative BigInt for walk-in accounts.

    Real Telegram IDs are always positive, so reserving the negative range
    for synthetic walk-in accounts guarantees no collision.  Uses microsecond
    timestamp for uniqueness; falls back to decrement-on-collision.
    """
    candidate = -int(time.time_ns() // 1000)
    # On the (extremely rare) collision, walk down until free
    while Account.objects.filter(telegram_id=candidate).exists():
        candidate -= 1
    return candidate


@transaction.atomic
def create_walkin_booking(
    *,
    full_name: str,
    phone: str,
    passport_number: str,
    room,
    branch,
    check_in_date,
    check_out_date,
    price_at_booking: Decimal,
    discount_amount: Decimal = Decimal("0"),
    performed_by=None,
) -> Booking:
    """
    Create a brand-new walk-in guest and their first booking atomically.

    Steps:
        1. Look up an existing Client by ``passport_number`` (idempotent).
        2. If not found, create a fresh Account (synthetic telegram_id) and
           Client profile.
        3. Delegate booking creation to :func:`create_booking`.
    """
    full_name = (full_name or "").strip()
    phone = (phone or "").strip()
    passport_number = (passport_number or "").strip()

    if not full_name:
        raise ValidationError({"full_name": "Full name is required."})
    if not phone:
        raise ValidationError({"phone": "Phone number is required."})
    if not passport_number:
        raise ValidationError({"passport_number": "Passport number is required."})

    client = Client.objects.select_related("account").filter(
        passport_number=passport_number
    ).first()

    if client is None:
        account = Account.objects.create(
            telegram_id=_next_synthetic_telegram_id(),
            phone=phone,
            is_active=True,
        )
        account.set_unusable_password()
        account.save(update_fields=["password"])

        client = Client.objects.create(
            account=account,
            full_name=full_name,
            passport_number=passport_number,
        )

        log_action(
            account=performed_by,
            action="account.created",
            entity_type="Account",
            entity_id=account.pk,
            after_data={
                "id": account.pk,
                "phone": account.phone,
                "telegram_id": account.telegram_id,
                "role": "client",
                "source": "walk_in",
            },
        )
        log_action(
            account=performed_by,
            action="client.created",
            entity_type="Client",
            entity_id=client.pk,
            after_data={
                "id": client.pk,
                "account_id": account.pk,
                "full_name": client.full_name,
                "passport_number": client.passport_number,
            },
        )
    else:
        # Existing returning guest — keep their record fresh (phone may change)
        if phone and client.account.phone != phone:
            client.account.phone = phone
            client.account.save(update_fields=["phone", "updated_at"])
        if full_name and client.full_name != full_name:
            client.full_name = full_name
            client.save(update_fields=["full_name"])

    return create_booking(
        client=client,
        room=room,
        branch=branch,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        price_at_booking=price_at_booking,
        discount_amount=discount_amount,
        performed_by=performed_by,
    )


# ==============================================================================
# EXTEND BOOKING (guest stays one or more extra nights)
# ==============================================================================


@transaction.atomic
def extend_booking(
    *,
    booking: Booking,
    new_check_out_date,
    additional_price: Decimal,
    performed_by=None,
) -> Booking:
    """
    Push the check-out date later and add the extra-night charge.

    Rules:
        - Only ``pending`` or ``paid`` bookings can be extended.
        - ``new_check_out_date`` must be strictly later than the current one.
        - The extended window must not overlap any other active booking
          on the same room.
        - ``additional_price`` is added to ``price_at_booking``; the discount
          is left untouched and ``final_price`` is recomputed.
    """
    if booking.status not in (
        Booking.BookingStatus.PENDING,
        Booking.BookingStatus.PAID,
    ):
        raise ValidationError(
            {"status": f"Cannot extend a booking with status '{booking.status}'."}
        )

    if new_check_out_date <= booking.check_out_date:
        raise ValidationError(
            {"new_check_out_date": "New check-out date must be after the current one."}
        )

    additional_price = Decimal(additional_price or 0)
    if additional_price < 0:
        raise ValidationError(
            {"additional_price": "Additional price cannot be negative."}
        )

    _validate_no_overlap(
        booking.room,
        booking.check_in_date,
        new_check_out_date,
        exclude_pk=booking.pk,
    )

    before = _booking_snapshot(booking)

    was_paid = booking.status == Booking.BookingStatus.PAID

    booking.check_out_date = new_check_out_date
    booking.price_at_booking = booking.price_at_booking + additional_price
    booking.final_price = _compute_final_price(
        booking.price_at_booking, booking.discount_amount
    )

    update_fields = [
        "check_out_date",
        "price_at_booking",
        "final_price",
        "updated_at",
    ]

    # If a fully-paid booking gets extended with a non-zero extra charge,
    # flip status back to ``pending`` so the admin can collect the balance.
    if was_paid and additional_price > 0:
        booking.status = Booking.BookingStatus.PENDING
        update_fields.append("status")

    booking.save(update_fields=update_fields)

    log_action(
        account=performed_by,
        action="booking.extended",
        entity_type="Booking",
        entity_id=booking.pk,
        before_data=before,
        after_data={
            **_booking_snapshot(booking),
            "additional_price": str(additional_price),
        },
    )
    notify_roles(
        roles=["administrator", "director"],
        branch=booking.branch,
        notification_type="booking",
        message=(
            f"Booking #{booking.pk} extended to {new_check_out_date} "
            f"(+{additional_price} UZS)."
        ),
    )

    return booking
