"""
Unit tests — Payment service layer.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.payments.services import record_payment

from conftest import BookingFactory


@pytest.mark.django_db
class TestRecordPayment:
    """Tests for record_payment()."""

    def test_records_payment_and_transitions_booking(self, booking):
        payment = record_payment(
            booking=booking,
            amount=Decimal("500000"),
            payment_type="manual",
        )
        assert payment.is_paid is True
        assert payment.paid_at is not None
        booking.refresh_from_db()
        assert booking.status == "paid"

    def test_idempotency_prevents_double_payment(self, booking):
        record_payment(
            booking=booking,
            amount=Decimal("500000"),
            payment_type="manual",
        )
        booking.refresh_from_db()
        with pytest.raises(ValidationError, match="Cannot pay"):
            record_payment(
                booking=booking,
                amount=Decimal("500000"),
                payment_type="manual",
            )

    def test_cannot_pay_canceled_booking(self, booking):
        booking.status = "canceled"
        booking.save()
        with pytest.raises(ValidationError, match="Cannot pay"):
            record_payment(
                booking=booking,
                amount=Decimal("500000"),
                payment_type="manual",
            )
