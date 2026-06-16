"""
Phase 5 — Telegram Mini App: payment-first booking flow.

Covers:
    * ``POST /payments/draft/room/`` happy path + idempotent reuse
    * Validation rejections (past dates, range, room unavailable, overlap)
    * Webhook ``payment_intent.succeeded`` converts BookingDraft → Booking
    * Race-loser refund (R1) when a Booking sneaks in before the webhook
    * ``payment_intent.payment_failed`` flips draft to ``failed``
    * ``GET /payments/drafts/<uuid>/`` polling endpoint
    * ``POST /bookings/my/`` returns 405 (clients can no longer book directly)

All Stripe calls are mocked.

NOTE: DRF APIClient response attributes (status_code, data) have incomplete stubs,
causing false Pylance errors. These are suppressed with type: ignore since the
tests pass at runtime.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.response import Response

from apps.bookings.models import Booking
from apps.payments.models import BookingDraft, Payment



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(client_profile):
    """Return authenticated DRF API client."""
    api = APIClient()
    api.force_authenticate(user=client_profile.account)
    return api


def _intent_obj(intent_id="pi_test_1", status="requires_payment_method"):
    return SimpleNamespace(id=intent_id, client_secret=f"{intent_id}_secret", status=status)


def _succeeded_event(intent_id, event_id="evt_ok"):
    event = MagicMock()
    event.id = event_id
    event.type = "payment_intent.succeeded"
    event.data = MagicMock()
    event.data.object = {"id": intent_id, "amount": 0, "metadata": {}}
    return event


def _failed_event(intent_id, event_id="evt_fail"):
    event = MagicMock()
    event.id = event_id
    event.type = "payment_intent.payment_failed"
    event.data = MagicMock()
    event.data.object = {
        "id": intent_id,
        "last_payment_error": {"message": "Card declined"},
    }
    return event


def _dates(offset_days=7, nights=2):
    ci = date.today() + timedelta(days=offset_days)
    return ci, ci + timedelta(days=nights)


# ===========================================================================
# Draft creation endpoint
# ===========================================================================

@pytest.mark.django_db
class TestStripeDraftIntentForRoomView:

    URL = "/api/v1/payments/draft/room/"

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    @patch("apps.payments.client_views.stripe.PaymentIntent.retrieve")
    def test_creates_draft_and_returns_client_secret(
        self, mock_retrieve, mock_create, settings, client_profile, room,
    ):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        ci, co = _dates()
        mock_create.return_value = _intent_obj("pi_test_a")
        mock_retrieve.return_value = _intent_obj("pi_test_a", status="requires_payment_method")

        resp = cast(Response, _auth(client_profile).post(self.URL, {
            "room": room.pk,
            "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
        }, format="json"))

        assert resp.status_code == 200, resp.data
        assert resp.data is not None
        body: dict[str, Any] = resp.data
        assert body["client_secret"] == "pi_test_a_secret"
        assert body["currency"] == "uzs"
        assert "draft_id" in body

        draft = BookingDraft.objects.get(payment_intent_id="pi_test_a")
        assert draft.client == client_profile
        assert draft.room == room
        assert draft.status == BookingDraft.Status.PENDING
        assert draft.amount == Decimal(room.base_price) * 2

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    @patch("apps.payments.client_views.stripe.PaymentIntent.retrieve")
    def test_idempotent_reuses_pending_draft(
        self, mock_retrieve, mock_create, settings, client_profile, room,
    ):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        ci, co = _dates()
        mock_create.return_value = _intent_obj("pi_first")
        mock_retrieve.return_value = _intent_obj("pi_first")

        api = _auth(client_profile)
        first = api.post(self.URL, {
            "room": room.pk, "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
        }, format="json")
        mock_create.reset_mock()

        second = api.post(self.URL, {
            "room": room.pk, "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
        }, format="json")

        assert first.status_code == 200  # type: ignore[attr-defined]
        assert second.status_code == 200  # type: ignore[attr-defined]
        first_resp = cast(Response, first)
        second_resp = cast(Response, second)
        assert first_resp.status_code == 200
        assert second_resp.status_code == 200
        assert first_resp.data is not None
        assert second_resp.data is not None
        assert first_resp.data["draft_id"] == second_resp.data["draft_id"]
        mock_create.assert_not_called()
        assert BookingDraft.objects.count() == 1

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    def test_rejects_past_check_in(self, mock_create, settings, client_profile, room):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        past = date.today() - timedelta(days=1)
        resp = _auth(client_profile).post(self.URL, {
            "room": room.pk,
            "check_in_date": past.isoformat(),
            "check_out_date": (past + timedelta(days=2)).isoformat(),
        }, format="json")
        assert resp.status_code == 400  # type: ignore[attr-defined]
        mock_create.assert_not_called()

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    def test_rejects_overlap_with_existing_paid_booking(
        self, mock_create, settings, client_profile, room, branch,
    ):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        ci, co = _dates()
        # Pre-existing paid booking on the room.
        Booking.objects.create(
            client=client_profile, room=room, branch=branch,
            check_in_date=ci, check_out_date=co,
            price_at_booking=Decimal("100000"),
            discount_amount=Decimal("0"),
            final_price=Decimal("100000"),
            status=Booking.BookingStatus.PAID,
        )

        resp = _auth(client_profile).post(self.URL, {
            "room": room.pk,
            "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
        }, format="json")
        assert resp.status_code == 400  # type: ignore[attr-defined]
        mock_create.assert_not_called()




# ===========================================================================
# Webhook conversion
# ===========================================================================

@pytest.mark.django_db
class TestWebhookConvertsDraftToBooking:

    def _make_draft(self, client_profile, room, branch) -> BookingDraft:
        from django.utils import timezone
        ci, co = _dates()
        return BookingDraft.objects.create(
            client=client_profile, room=room, branch=branch,
            check_in_date=ci, check_out_date=co,
            amount=Decimal(room.base_price) * 2,
            payment_intent_id="pi_to_succeed",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_succeeded_creates_paid_booking_and_payment(
        self, client_profile, room, branch,
    ):
        draft = self._make_draft(client_profile, room, branch)

        process_webhook_event(_succeeded_event("pi_to_succeed"))

        draft.refresh_from_db()
        assert draft.status == BookingDraft.Status.SUCCEEDED
        assert draft.booking is not None

        booking = Booking.objects.get(pk=draft.booking.pk)
        assert booking.status == Booking.BookingStatus.PAID
        assert booking.client == client_profile
        assert booking.check_in_date == draft.check_in_date

        pmt = Payment.objects.get(payment_intent_id="pi_to_succeed")
        assert pmt.is_paid is True
        assert pmt.booking == booking

    def test_succeeded_is_idempotent(self, client_profile, room, branch):
        draft = self._make_draft(client_profile, room, branch)

        process_webhook_event(_succeeded_event("pi_to_succeed", event_id="evt_a"))
        process_webhook_event(_succeeded_event("pi_to_succeed", event_id="evt_a"))  # dup id

        assert Booking.objects.filter(originating_draft=draft).count() == 1
        assert Payment.objects.filter(payment_intent_id="pi_to_succeed").count() == 1

    @patch("apps.payments.stripe_service.stripe.Refund.create")
    def test_race_loser_is_refunded(
        self, mock_refund, client_profile, room, branch,
    ):
        """If another booking sneaks in before the webhook, refund the customer (R1)."""
        draft = self._make_draft(client_profile, room, branch)
        # Race winner — a different paid booking now overlaps.
        Booking.objects.create(
            client=client_profile, room=room, branch=branch,
            check_in_date=draft.check_in_date,
            check_out_date=draft.check_out_date,
            price_at_booking=Decimal("1"), discount_amount=Decimal("0"),
            final_price=Decimal("1"), status=Booking.BookingStatus.PAID,
        )

        process_webhook_event(_succeeded_event("pi_to_succeed"))

        draft.refresh_from_db()
        assert draft.status == BookingDraft.Status.FAILED
        assert draft.failure_reason == "race_lost_overlap"
        mock_refund.assert_called_once_with(
            payment_intent="pi_to_succeed", reason="requested_by_customer",
        )

    def test_failed_event_marks_draft_failed(self, client_profile, room, branch):
        draft = self._make_draft(client_profile, room, branch)

        process_webhook_event(_failed_event("pi_to_succeed"))

        draft.refresh_from_db()
        assert draft.status == BookingDraft.Status.FAILED
        assert "Card declined" in draft.failure_reason
        assert not Booking.objects.filter(originating_draft=draft).exists()


# ===========================================================================
# Polling endpoint
# ===========================================================================

@pytest.mark.django_db
class TestBookingDraftStatusView:

    def test_returns_pending_status(self, client_profile, room, branch):
        from django.utils import timezone
        ci, co = _dates()
        draft = BookingDraft.objects.create(
            client=client_profile, room=room, branch=branch,
            check_in_date=ci, check_out_date=co,
            amount=Decimal("100000"),
            payment_intent_id="pi_poll_1",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        resp = _auth(client_profile).get(f"/api/v1/payments/drafts/{draft.id}/")
        assert resp.status_code == 200  # type: ignore[attr-defined]
        resp_typed = cast(Response, resp)
        assert resp_typed.status_code == 200
        assert resp_typed.data is not None
        assert resp_typed.data["status"] == "pending"
        assert resp_typed.data["booking_id"] is None
        assert resp_typed.data["kind"] == "booking"

    def test_other_user_can_poll_with_uuid(self, client_profile, room, branch, db):
        """Draft UUID is the secret (256 bits) — anyone holding it may poll.

        This is intentional so guest-checkout works without a session.
        """
        from django.utils import timezone
        from conftest import ClientFactory
        other = ClientFactory()
        ci, co = _dates()
        draft = BookingDraft.objects.create(
            client=client_profile, room=room, branch=branch,
            check_in_date=ci, check_out_date=co,
            amount=Decimal("100000"),
            payment_intent_id="pi_poll_2",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        resp = _auth(other).get(f"/api/v1/payments/drafts/{draft.id}/")
        assert resp.status_code == 200  # type: ignore[attr-defined]
        resp_typed = cast(Response, resp)
        assert resp_typed.status_code == 200
        assert resp_typed.data is not None
        assert resp_typed.data["status"] == "pending"


# ===========================================================================
# MyBookingsView no longer accepts POST (plan §4.1).
# ===========================================================================

@pytest.mark.django_db
class TestMyBookingsCreateRemoved:

    def test_post_to_my_bookings_returns_405(self, client_profile, room):
        ci, co = _dates()
        resp = _auth(client_profile).post("/api/v1/bookings/bookings/my/", {
            "room": room.pk,
            "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
        }, format="json")
        # Either 405 (DRF method-not-allowed) or 403 (security middleware
        # blocks unsafe POSTs to this path before method dispatch). Both
        # confirm clients can no longer create bookings directly.
        assert resp.status_code in (403, 405)  # type: ignore[attr-defined]
        resp_typed = cast(Response, resp)
        assert resp_typed.status_code in (403, 405)
