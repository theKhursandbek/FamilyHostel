"""
Phase 8 hardening — ``reap_stale_drafts`` Celery task (D12).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.bookings.models import Booking
from apps.payments.models import BookingDraft, ExtensionDraft
from apps.payments.tasks import reap_stale_drafts


def _booking_draft(client_profile, room, branch, *, expires_at, intent_id):
    ci = date.today() + timedelta(days=5)
    return BookingDraft.objects.create(
        client=client_profile,
        room=room,
        branch=branch,
        check_in_date=ci,
        check_out_date=ci + timedelta(days=2),
        amount=Decimal("400000"),
        currency="UZS",
        payment_intent_id=intent_id,
        status=BookingDraft.Status.PENDING,
        expires_at=expires_at,
    )


@pytest.mark.django_db
def test_reap_cancels_expired_booking_draft(client_profile, room, branch):
    expired = _booking_draft(
        client_profile, room, branch,
        expires_at=timezone.now() - timedelta(minutes=1),
        intent_id="pi_expired_1",
    )
    fresh = _booking_draft(
        client_profile, room, branch,
        expires_at=timezone.now() + timedelta(minutes=5),
        intent_id="pi_fresh_1",
    )

    with patch("stripe.PaymentIntent.cancel") as mock_cancel:
        result = reap_stale_drafts()

    expired.refresh_from_db()
    fresh.refresh_from_db()
    assert expired.status == BookingDraft.Status.CANCELED
    assert expired.failure_reason == "expired"
    assert fresh.status == BookingDraft.Status.PENDING
    mock_cancel.assert_called_once_with("pi_expired_1")
    assert result["booking"] == 1
    assert result["extension"] == 0


@pytest.mark.django_db
def test_reap_swallows_stripe_errors(client_profile, room, branch):
    expired = _booking_draft(
        client_profile, room, branch,
        expires_at=timezone.now() - timedelta(minutes=10),
        intent_id="pi_boom",
    )

    with patch("stripe.PaymentIntent.cancel", side_effect=Exception("already canceled")):
        result = reap_stale_drafts()

    expired.refresh_from_db()
    assert expired.status == BookingDraft.Status.CANCELED
    assert result["booking"] == 1


@pytest.mark.django_db
def test_reap_handles_extension_drafts(client_profile, room, branch):
    booking = Booking.objects.create(
        client=client_profile, room=room, branch=branch,
        check_in_date=date.today() + timedelta(days=1),
        check_out_date=date.today() + timedelta(days=3),
        price_at_booking=Decimal("400000"),
        final_price=Decimal("400000"),
        status="paid",
    )
    draft = ExtensionDraft.objects.create(
        booking=booking,
        new_check_out_date=booking.check_out_date + timedelta(days=2),
        amount=Decimal("400000"), currency="UZS",
        payment_intent_id="pi_ext_expired",
        status=ExtensionDraft.Status.PENDING,
        expires_at=timezone.now() - timedelta(seconds=30),
    )

    with patch("stripe.PaymentIntent.cancel"):
        result = reap_stale_drafts()

    draft.refresh_from_db()
    assert draft.status == ExtensionDraft.Status.CANCELED
    assert result["extension"] == 1
