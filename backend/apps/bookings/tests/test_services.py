"""
Unit tests — Booking service layer.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.bookings.services import cancel_booking, complete_booking, create_booking
from apps.branches.models import Room
from apps.payments.services import record_payment

from conftest import BookingFactory, ClientFactory, RoomFactory


@pytest.mark.django_db
class TestCreateBooking:
    """Tests for create_booking()."""

    def test_creates_booking_with_correct_fields(self, client_profile, room, branch):
        booking = create_booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=datetime.date(2026, 5, 1),
            check_out_date=datetime.date(2026, 5, 5),
            price_at_booking=Decimal("400000"),
            discount_amount=Decimal("10000"),
        )
        assert booking.pk is not None
        assert booking.status == "pending"
        assert booking.final_price == Decimal("390000")

    def test_room_marked_as_booked(self, client_profile, room, branch):
        create_booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=datetime.date(2026, 6, 1),
            check_out_date=datetime.date(2026, 6, 3),
            price_at_booking=Decimal("200000"),
        )
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.BOOKED

    def test_overlap_rejected(self, client_profile, room, branch):
        create_booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=datetime.date(2026, 7, 1),
            check_out_date=datetime.date(2026, 7, 5),
            price_at_booking=Decimal("300000"),
        )
        client2 = ClientFactory()
        with pytest.raises(ValidationError, match="overlapping"):
            create_booking(
                client=client2,
                room=room,
                branch=branch,
                check_in_date=datetime.date(2026, 7, 3),
                check_out_date=datetime.date(2026, 7, 7),
                price_at_booking=Decimal("300000"),
            )

    def test_checkout_before_checkin_rejected(self, client_profile, room, branch):
        with pytest.raises(ValidationError, match="after check-in"):
            create_booking(
                client=client_profile,
                room=room,
                branch=branch,
                check_in_date=datetime.date(2026, 8, 5),
                check_out_date=datetime.date(2026, 8, 1),
                price_at_booking=Decimal("200000"),
            )

    def test_discount_exceeds_price_rejected(self, client_profile, room, branch):
        with pytest.raises(ValidationError, match="exceed"):
            create_booking(
                client=client_profile,
                room=room,
                branch=branch,
                check_in_date=datetime.date(2026, 9, 1),
                check_out_date=datetime.date(2026, 9, 3),
                price_at_booking=Decimal("10000"),
                discount_amount=Decimal("20000"),
            )


@pytest.mark.django_db
class TestCancelBooking:
    """Tests for cancel_booking()."""

    def test_cancel_pending_booking(self, booking):
        result = cancel_booking(booking)
        assert result.status == "canceled"
        booking.room.refresh_from_db()
        assert booking.room.status == Room.RoomStatus.AVAILABLE

    def test_cancel_paid_booking_no_refund(self, booking):
        """Plan D6: paid bookings can be canceled, but money is never refunded."""
        from apps.payments.models import Payment

        booking.status = "paid"
        booking.save()
        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type=Payment.PaymentType.ONLINE,
            is_paid=True,
            payment_intent_id="pi_test_existing",
        )

        result = cancel_booking(booking)

        assert result.status == "canceled"
        booking.room.refresh_from_db()
        assert booking.room.status == Room.RoomStatus.AVAILABLE
        # The original payment row is left intact and no refund row is added.
        assert Payment.objects.filter(booking=booking).count() == 1
        original = Payment.objects.get(booking=booking)
        assert original.is_paid is True
        assert original.amount == booking.final_price

    def test_cannot_cancel_completed_booking(self, booking):
        booking.status = "completed"
        booking.save()
        with pytest.raises(ValidationError, match="Cannot cancel"):
            cancel_booking(booking)


@pytest.mark.django_db
class TestCompleteBooking:
    """Tests for complete_booking()."""

    def test_complete_paid_booking(self, booking):
        booking.status = "paid"
        booking.save()
        result = complete_booking(booking)
        assert result.status == "completed"
        booking.room.refresh_from_db()
        assert booking.room.status == Room.RoomStatus.CLEANING

    def test_cannot_complete_pending_booking(self, booking):
        with pytest.raises(ValidationError, match="Only paid"):
            complete_booking(booking)

    def test_creates_cleaning_task(self, booking):
        booking.status = "paid"
        booking.save()
        complete_booking(booking)
        from apps.cleaning.models import CleaningTask

        task = CleaningTask.objects.filter(room=booking.room).first()
        assert task is not None
        assert task.status == "pending"
