"""
E2E test — Full booking lifecycle.

Booking → Payment → Complete → Cleaning Task → Assign → Complete

This verifies the entire business flow works end-to-end
through the service layer.
"""

import datetime
from decimal import Decimal

import pytest

from apps.bookings.models import Booking
from apps.bookings.services import complete_booking, create_booking
from apps.branches.models import Room
from apps.cleaning.models import CleaningTask
from apps.cleaning.services import assign_task_to_staff, complete_task
from apps.payments.services import record_payment

from conftest import ClientFactory, RoomFactory, StaffFactory


@pytest.mark.e2e
@pytest.mark.django_db
class TestBookingToCleaningFlow:
    """Full lifecycle: Booking → Payment → Checkout → Cleaning → Done."""

    def test_full_lifecycle(self, client_profile, room, branch, staff_profile):
        # ── 1. Create booking ───────────────────────────────────
        booking = create_booking(
            client=client_profile,
            room=room,
            branch=branch,
            check_in_date=datetime.date(2026, 11, 1),
            check_out_date=datetime.date(2026, 11, 5),
            price_at_booking=Decimal("600000"),
            discount_amount=Decimal("50000"),
        )
        assert booking.status == "pending"
        assert booking.final_price == Decimal("550000")
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.BOOKED

        # ── 2. Record payment ──────────────────────────────────
        payment = record_payment(
            booking=booking,
            amount=Decimal("550000"),
            payment_type="manual",
        )
        assert payment.is_paid is True
        booking.refresh_from_db()
        assert booking.status == "paid"

        # ── 3. Complete booking (guest checks out) ─────────────
        complete_booking(booking)
        booking.refresh_from_db()
        assert booking.status == "completed"
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.CLEANING

        # ── 4. Cleaning task auto-created ──────────────────────
        task = CleaningTask.objects.get(room=room)
        assert task.status == "pending"

        # ── 5. Staff picks the task ────────────────────────────
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.refresh_from_db()
        assert task.status == "in_progress"
        assert task.assigned_to == staff_profile

        # ── 6. Staff completes cleaning ────────────────────────
        complete_task(task=task)
        task.refresh_from_db()
        assert task.status == "completed"
        assert task.completed_at is not None
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.AVAILABLE

        # ── Final verification ─────────────────────────────────
        # Room is back to available, ready for next guest
        assert Booking.objects.filter(pk=booking.pk, status="completed").exists()
