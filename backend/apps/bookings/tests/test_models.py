"""
Unit tests — Booking model validations.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.bookings.models import Booking

from conftest import BookingFactory, ClientFactory, RoomFactory


@pytest.mark.django_db
class TestBookingModelValidation:
    """Test model-level constraints and validators."""

    def test_checkout_must_be_after_checkin(self, client_profile, room, branch):
        """DB CheckConstraint: check_out_date > check_in_date."""
        today = datetime.date.today()
        with pytest.raises(IntegrityError):
            Booking.objects.create(
                client=client_profile,
                room=room,
                branch=branch,
                check_in_date=today,
                check_out_date=today,  # same day — violates constraint
                price_at_booking=Decimal("100000"),
                discount_amount=Decimal("0"),
                final_price=Decimal("100000"),
            )

    def test_discount_max_50000(self, client_profile, room, branch):
        """Model validator: discount_amount <= 50,000 UZS."""
        today = datetime.date.today()
        booking = Booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=today,
            check_out_date=today + datetime.timedelta(days=1),
            price_at_booking=Decimal("500000"),
            discount_amount=Decimal("60000"),  # exceeds 50k
            final_price=Decimal("440000"),
        )
        with pytest.raises(ValidationError):
            booking.full_clean()

    def test_final_price_cannot_be_negative(self, client_profile, room, branch):
        """Model validator: final_price >= 0."""
        today = datetime.date.today()
        booking = Booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=today,
            check_out_date=today + datetime.timedelta(days=1),
            price_at_booking=Decimal("10000"),
            discount_amount=Decimal("0"),
            final_price=Decimal("-1"),
        )
        with pytest.raises(ValidationError):
            booking.full_clean()

    def test_status_choices(self):
        """Booking statuses match README Section 19."""
        choices = {c[0] for c in Booking.BookingStatus.choices}
        assert choices == {"pending", "paid", "canceled"}

    def test_default_status_is_pending(self, client_profile, room, branch):
        """New bookings default to pending."""
        today = datetime.date.today()
        booking = Booking.objects.create(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=today,
            check_out_date=today + datetime.timedelta(days=2),
            price_at_booking=Decimal("200000"),
            discount_amount=Decimal("0"),
            final_price=Decimal("200000"),
        )
        assert booking.status == "pending"
