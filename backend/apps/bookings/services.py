"""
Booking service layer — business logic for creating, updating, and canceling bookings.

Functions define the contract between the API layer (views/serializers) and
the model layer. All state transitions and validations live here.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.branches.models import Room

from .models import Booking

if TYPE_CHECKING:
    from apps.accounts.models import Account, Client
    from apps.branches.models import Branch


def create_booking(
    client: Client,
    room: Room,
    branch: Branch,
    check_in_date: datetime.date,
    check_out_date: datetime.date,
    price_at_booking: Decimal,
    discount_amount: Decimal = Decimal("0"),
    source: str = Booking.BookingSource.MANUAL,
    performed_by: Account | None = None,
) -> Booking:
    """
    Create a new booking for a client in a room.

    Validations:
        - check_out_date must be after check_in_date
        - discount_amount must not exceed price_at_booking
        - room must not have overlapping bookings (pending or paid)
        - discount_amount must not exceed 50,000 UZS

    Business logic:
        - Mark the room as BOOKED
        - Calculate final_price = price_at_booking - discount_amount
        - Set status to PENDING

    Args:
        client: The client profile
        room: The room to book
        branch: The branch
        check_in_date: Check-in date (YYYY-MM-DD)
        check_out_date: Check-out date (YYYY-MM-DD)
        price_at_booking: Price at time of booking
        discount_amount: Discount amount (default 0)
        source: Booking source (manual or telegram, default manual)
        performed_by: Account that created the booking (optional, for audit)

    Returns:
        The newly created Booking instance

    Raises:
        ValidationError: If any validation fails
    """
    # Validate dates
    if check_out_date <= check_in_date:
        raise ValidationError(
            {"check_out_date": "Check-out date must be after check-in date."}
        )

    # Validate discount
    if discount_amount < 0:
        raise ValidationError(
            {"discount_amount": "Discount amount cannot be negative."}
        )
    if discount_amount > price_at_booking:
        raise ValidationError(
            {"discount_amount": "Discount amount cannot exceed the room price."}
        )

    # Check for overlapping bookings
    overlapping = Booking.objects.filter(
        room=room,
        status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
        check_in_date__lt=check_out_date,
        check_out_date__gt=check_in_date,
    ).exists()
    if overlapping:
        raise ValidationError(
            {
                "detail": (
                    f"Room {room.room_number} has an overlapping booking on "
                    f"those dates."
                )
            }
        )

    # Calculate final price
    final_price = price_at_booking - discount_amount

    # Create booking
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
        source=source,
    )

    # Mark room as booked
    room.status = Room.RoomStatus.BOOKED
    room.save(update_fields=["status"])

    return booking


def cancel_booking(
    booking: Booking,
    performed_by: Account | None = None,
) -> Booking:
    """
    Cancel an existing booking.

    Business rules (README Section 4):
        - Pending bookings: set status to CANCELED, room back to AVAILABLE
        - Paid bookings: set status to CANCELED, room back to AVAILABLE
          BUT no refund is issued (Plan D6)
        - Completed / canceled: cannot cancel (raises ValidationError)

    Args:
        booking: The booking instance to cancel
        performed_by: Account that performed the cancellation (optional, for audit)

    Returns:
        The updated Booking instance

    Raises:
        ValidationError: If booking cannot be canceled (already completed/canceled)
    """
    if booking.status in [
        Booking.BookingStatus.COMPLETED,
        Booking.BookingStatus.CANCELED,
    ]:
        raise ValidationError(
            {
                "detail": (
                    f"Cannot cancel a {booking.status} booking. "
                    "Only pending or paid bookings can be canceled."
                )
            }
        )

    # Update booking status
    booking.status = Booking.BookingStatus.CANCELED
    booking.save(update_fields=["status"])

    # Mark room as available
    booking.room.status = Room.RoomStatus.AVAILABLE
    booking.room.save(update_fields=["status"])

    return booking


def complete_booking(
    booking: Booking,
    performed_by: Account | None = None,
) -> Booking:
    """
    Complete (check out) a paid booking.

    This transitions a booking from PAID to COMPLETED and triggers the
    cleaning workflow (room moved to CLEANING status, which auto-creates
    a cleaning task via signal).

    Business rules (README Section 4):
        - Only PAID bookings can be completed
        - Pending, canceled, or already completed: raises ValidationError
        - Room is moved to CLEANING status
        - A CleaningTask is auto-created via signal

    Args:
        booking: The booking instance to complete
        performed_by: Account that performed the completion (optional, for audit)

    Returns:
        The updated Booking instance

    Raises:
        ValidationError: If booking is not in PAID status
    """
    if booking.status != Booking.BookingStatus.PAID:
        raise ValidationError(
            {
                "detail": (
                    "Only paid bookings can be completed. "
                    f"This booking is {booking.status}."
                )
            }
        )

    # Update booking status
    booking.status = Booking.BookingStatus.COMPLETED
    booking.save(update_fields=["status"])

    # Mark room as cleaning (signal will auto-create a cleaning task)
    booking.room.status = Room.RoomStatus.CLEANING
    booking.room.save(update_fields=["status"])

    return booking


def create_walkin_booking(
    full_name: str,
    phone: str,
    passport_number: str,
    room: Room,
    branch: Branch,
    check_in_date: datetime.date,
    check_out_date: datetime.date,
    price_at_booking: Decimal,
    discount_amount: Decimal = Decimal("0"),
    performed_by: Account | None = None,
) -> Booking:
    """
    Create a walk-in booking (admin creates new guest + booking atomically).

    This is the POST /bookings/bookings/walk-in/ endpoint that the admin
    panel uses to create a guest + booking in one step.

    Args:
        full_name: Guest's full name
        phone: Guest's phone number
        passport_number: Guest's passport number
        room: The room to book
        branch: The branch
        check_in_date: Check-in date
        check_out_date: Check-out date
        price_at_booking: Price at booking time
        discount_amount: Discount (default 0)
        performed_by: Account that created the booking (optional)

    Returns:
        The newly created Booking instance

    Raises:
        ValidationError: If validation fails
    """
    from apps.accounts.models import Client, Account

    # Create a new client account and profile
    # The account phone must be unique; check if one already exists
    existing_account = Account.objects.filter(phone=phone).first()
    if existing_account and existing_account.client_profile:
        client_profile = existing_account.client_profile
    else:
        # Create a new account + client profile
        account = Account.objects.create(
            phone=phone,
            is_active=True,
        )
        client_profile = Client.objects.create(
            account=account,
            full_name=full_name,
            passport_number=passport_number,
            date_of_birth=None,  # Walk-in guests don't provide DOB
        )

    # Now create the booking using the standard create_booking function
    booking = create_booking(
        client=client_profile,
        room=room,
        branch=branch,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        price_at_booking=price_at_booking,
        discount_amount=discount_amount,
        source=Booking.BookingSource.MANUAL,
        performed_by=performed_by,
    )

    return booking
