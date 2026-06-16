"""
Tests for the booking-system overhaul:

    - per-branch booking numbers (branch_number)
    - extension lifecycle (BookingExtension) + partial cancellation
    - auto-cancellation of stale unpaid bookings
    - strict guest validators
    - availability + cancel-extension API actions
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers as drf_serializers

from apps.bookings.models import Booking, BookingExtension
from apps.bookings.services import (
    allocate_branch_number,
    cancel_extension,
    create_booking,
    extend_booking,
)
from apps.common import validators as v
from apps.payments.services import paid_total, record_payment

from conftest import BookingFactory, ClientFactory, RoomFactory

TODAY = datetime.date.today()
DAY = datetime.timedelta(days=1)


# ==============================================================================
# Per-branch numbering
# ==============================================================================


@pytest.mark.django_db
class TestBranchNumber:
    def test_sequential_per_branch(self, branch, room_type):
        r1 = RoomFactory(branch=branch, room_type=room_type)
        r2 = RoomFactory(branch=branch, room_type=room_type)
        b1 = create_booking(
            client=ClientFactory(), room=r1, branch=branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            price_at_booking=Decimal("100000"),
        )
        b2 = create_booking(
            client=ClientFactory(), room=r2, branch=branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            price_at_booking=Decimal("100000"),
        )
        assert b1.branch_number == 1
        assert b2.branch_number == 2

    def test_independent_across_branches(self, branch, room, room_type):
        other_branch_room = RoomFactory(room_type=room_type)  # new branch
        b1 = create_booking(
            client=ClientFactory(), room=room, branch=room.branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            price_at_booking=Decimal("100000"),
        )
        b2 = create_booking(
            client=ClientFactory(), room=other_branch_room,
            branch=other_branch_room.branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            price_at_booking=Decimal("100000"),
        )
        # Each branch starts its own sequence at #1.
        assert b1.branch_number == 1
        assert b2.branch_number == 1

    def test_allocate_helper_starts_at_one(self, branch):
        assert allocate_branch_number(branch) == 1


# ==============================================================================
# Extension lifecycle
# ==============================================================================


@pytest.mark.django_db
class TestExtensionLifecycle:
    def _booking(self, **kw):
        defaults = {
            "check_in_date": TODAY + DAY,
            "check_out_date": TODAY + 3 * DAY,
            "price_at_booking": Decimal("300000"),
            "final_price": Decimal("300000"),
            "status": Booking.BookingStatus.PENDING,
        }
        defaults.update(kw)
        return BookingFactory(**defaults)

    def test_extend_records_active_extension(self):
        booking = self._booking()
        before_co = booking.check_out_date
        extend_booking(
            booking=booking,
            new_check_out_date=before_co + 2 * DAY,
            additional_price=Decimal("200000"),
        )
        ext = booking.extensions.get()
        assert ext.status == BookingExtension.ExtensionStatus.ACTIVE
        assert ext.previous_check_out_date == before_co
        assert ext.new_check_out_date == before_co + 2 * DAY
        assert ext.additional_price == Decimal("200000")
        booking.refresh_from_db()
        assert booking.check_out_date == before_co + 2 * DAY
        assert booking.price_at_booking == Decimal("500000")

    def test_extend_never_changes_source(self):
        booking = self._booking(source=Booking.BookingSource.TELEGRAM)
        extend_booking(
            booking=booking,
            new_check_out_date=booking.check_out_date + DAY,
            additional_price=Decimal("100000"),
        )
        booking.refresh_from_db()
        assert booking.source == Booking.BookingSource.TELEGRAM

    def test_cancel_extension_rolls_back_only_delta(self):
        booking = self._booking()
        original_co = booking.check_out_date
        original_price = booking.price_at_booking
        extend_booking(
            booking=booking,
            new_check_out_date=original_co + 2 * DAY,
            additional_price=Decimal("200000"),
        )
        cancel_extension(booking=booking)
        booking.refresh_from_db()
        assert booking.check_out_date == original_co
        assert booking.price_at_booking == original_price
        ext = booking.extensions.get()
        assert ext.status == BookingExtension.ExtensionStatus.CANCELED
        assert ext.canceled_at is not None

    def test_cancel_extension_requires_active(self):
        booking = self._booking()
        with pytest.raises(DjangoValidationError):
            cancel_extension(booking=booking)

    def test_paid_then_extend_then_cancel_restores_paid(self, admin_profile):
        booking = self._booking(status=Booking.BookingStatus.PENDING)
        # Pay it off fully → status paid.
        record_payment(
            booking=booking, amount=booking.final_price,
            payment_type="manual", created_by=admin_profile.account,
        )
        booking.refresh_from_db()
        assert booking.status == Booking.BookingStatus.PAID

        # Extend with a real charge → flips back to pending.
        extend_booking(
            booking=booking,
            new_check_out_date=booking.check_out_date + DAY,
            additional_price=Decimal("150000"),
        )
        booking.refresh_from_db()
        assert booking.status == Booking.BookingStatus.PENDING

        # Cancel the extension → base is covered again → paid restored.
        cancel_extension(booking=booking)
        booking.refresh_from_db()
        assert booking.status == Booking.BookingStatus.PAID
        # No refund: the original payment is untouched.
        assert paid_total(booking) == Decimal("300000")


# ==============================================================================
# Strict guest validators (ported from the Telegram Mini App)
# ==============================================================================


class TestValidators:
    def test_full_name_ok(self):
        assert v.validate_full_name("Botir Aliyev") == "Botir Aliyev"

    @pytest.mark.parametrize("bad", ["Bo", "Botir", "John123", "Bo Al", "A B"])
    def test_full_name_rejects(self, bad):
        with pytest.raises(drf_serializers.ValidationError):
            v.validate_full_name(bad)

    def test_phone_normalises(self):
        assert v.validate_uz_phone("998901234567") == "+998901234567"
        assert v.validate_uz_phone("+998 90 123 45 67") == "+998901234567"

    @pytest.mark.parametrize("bad", ["+99890123456", "+12345678901", "abc"])
    def test_phone_rejects(self, bad):
        with pytest.raises(drf_serializers.ValidationError):
            v.validate_uz_phone(bad)

    def test_passport_uppercases(self):
        assert v.validate_passport("ab1234567") == "AB1234567"

    @pytest.mark.parametrize("bad", ["ABC1234567", "A1234567", "AB123456", "1234567AB"])
    def test_passport_rejects(self, bad):
        with pytest.raises(drf_serializers.ValidationError):
            v.validate_passport(bad)

    def test_dob_ok_at_min_age(self):
        dob = TODAY.replace(year=TODAY.year - 20)
        assert v.validate_dob(dob) == dob

    def test_dob_too_young(self):
        dob = TODAY.replace(year=TODAY.year - 10)
        with pytest.raises(drf_serializers.ValidationError):
            v.validate_dob(dob)

    def test_dob_future_rejected(self):
        with pytest.raises(drf_serializers.ValidationError):
            v.validate_dob(TODAY + 365 * DAY)


# ==============================================================================
# API actions
# ==============================================================================


@pytest.mark.django_db
class TestAvailabilityAPI:
    def test_returns_booked_ranges(self, admin_client, admin_profile, room):
        branch = admin_profile.branch
        room.branch = branch
        room.save(update_fields=["branch"])
        booking = BookingFactory(
            room=room, branch=branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            status=Booking.BookingStatus.PAID,
        )
        url = reverse("bookings:booking-availability")
        resp = admin_client.get(url, {"room": room.pk})
        assert resp.status_code == 200
        ranges = resp.data["booked_ranges"]
        assert any(r["id"] == booking.pk for r in ranges)

    def test_excludes_given_pk(self, admin_client, admin_profile, room):
        branch = admin_profile.branch
        room.branch = branch
        room.save(update_fields=["branch"])
        booking = BookingFactory(
            room=room, branch=branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            status=Booking.BookingStatus.PAID,
        )
        url = reverse("bookings:booking-availability")
        resp = admin_client.get(url, {"room": room.pk, "exclude": booking.pk})
        assert resp.status_code == 200
        assert resp.data["booked_ranges"] == []


@pytest.mark.django_db
class TestCancelExtensionAPI:
    def test_cancel_extension_endpoint(self, admin_client, admin_profile, room):
        branch = admin_profile.branch
        room.branch = branch
        room.save(update_fields=["branch"])
        booking = BookingFactory(
            room=room, branch=branch,
            check_in_date=TODAY + DAY, check_out_date=TODAY + 3 * DAY,
            price_at_booking=Decimal("300000"), final_price=Decimal("300000"),
            status=Booking.BookingStatus.PENDING,
        )
        original_co = booking.check_out_date
        extend_booking(
            booking=booking,
            new_check_out_date=original_co + 2 * DAY,
            additional_price=Decimal("200000"),
        )
        url = reverse("bookings:booking-cancel-extension", args=[booking.pk])
        resp = admin_client.post(url)
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.check_out_date == original_co
        assert booking.extensions.get().status == "canceled"
