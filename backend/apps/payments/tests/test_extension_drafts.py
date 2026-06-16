"""
Phase 7 — ExtensionDraft (extend a paid booking via Stripe).

Covers:
    * ``POST /payments/draft/extension/`` happy path + validation
    * Webhook converts ExtensionDraft → bumped check_out_date + Payment row
    * Race-loser refund (R1) when an overlapping booking sneaks in
    * ``GET /payments/drafts/<uuid>/`` returns kind="extension"
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.payments.models import ExtensionDraft, Payment
from apps.payments.stripe_service import process_webhook_event


def _auth(client_profile) -> APIClient:
    api = APIClient()
    api.force_authenticate(user=client_profile.account)
    return api


def _intent_obj(intent_id="pi_ext_1"):
    return SimpleNamespace(id=intent_id, client_secret=f"{intent_id}_secret",
                           status="requires_payment_method")


def _succeeded_event(intent_id):
    return SimpleNamespace(
        id=f"evt_{intent_id}",
        type="payment_intent.succeeded",
        data=SimpleNamespace(object={"id": intent_id, "amount": 0, "metadata": {}}),
    )


def _make_paid_booking(client_profile, room, branch, *, nights=2):
    ci = date.today() + timedelta(days=2)
    co = ci + timedelta(days=nights)
    return Booking.objects.create(
        client=client_profile, room=room, branch=branch,
        check_in_date=ci, check_out_date=co,
        price_at_booking=Decimal(room.base_price) * nights,
        discount_amount=Decimal("0"),
        final_price=Decimal(room.base_price) * nights,
        status=Booking.BookingStatus.PAID,
    )


# ===========================================================================
# Endpoint
# ===========================================================================

@pytest.mark.django_db
class TestExtensionIntentEndpoint:

    URL = "/api/v1/payments/draft/extension/"

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    @patch("apps.payments.client_views.stripe.PaymentIntent.retrieve")
    def test_happy_path_creates_extension_draft(
        self, mock_retrieve, mock_create, settings, client_profile, room, branch,
    ):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        booking = _make_paid_booking(client_profile, room, branch)
        new_co = booking.check_out_date + timedelta(days=2)
        mock_create.return_value = _intent_obj("pi_ext_ok")
        mock_retrieve.return_value = _intent_obj("pi_ext_ok")

        resp = _auth(client_profile).post(self.URL, {
            "booking": booking.pk,
            "new_check_out_date": new_co.isoformat(),
        }, format="json")

        assert resp.status_code == 200, resp.data
        body = resp.data
        assert "draft_id" in body and body["client_secret"]

        draft = ExtensionDraft.objects.get(payment_intent_id="pi_ext_ok")
        assert draft.booking == booking
        assert draft.new_check_out_date == new_co
        assert draft.amount == Decimal(room.base_price) * 2

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    def test_rejects_pending_booking(self, mock_create, settings, client_profile, room, branch):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        booking = _make_paid_booking(client_profile, room, branch)
        booking.status = Booking.BookingStatus.PENDING
        booking.save(update_fields=["status"])

        resp = _auth(client_profile).post(self.URL, {
            "booking": booking.pk,
            "new_check_out_date": (booking.check_out_date + timedelta(days=1)).isoformat(),
        }, format="json")
        assert resp.status_code == 400
        mock_create.assert_not_called()

    @patch("apps.payments.draft_service.stripe.PaymentIntent.create")
    def test_rejects_new_date_not_after_current(
        self, mock_create, settings, client_profile, room, branch,
    ):
        settings.STRIPE_SECRET_KEY = "sk_test_" + ("a" * 60)
        booking = _make_paid_booking(client_profile, room, branch)

        resp = _auth(client_profile).post(self.URL, {
            "booking": booking.pk,
            "new_check_out_date": booking.check_out_date.isoformat(),
        }, format="json")
        assert resp.status_code == 400
        mock_create.assert_not_called()

    def test_other_user_gets_404(self, client_profile, room, branch, db):
        from conftest import ClientFactory
        booking = _make_paid_booking(client_profile, room, branch)
        other = ClientFactory()

        resp = _auth(other).post(self.URL, {
            "booking": booking.pk,
            "new_check_out_date": (booking.check_out_date + timedelta(days=1)).isoformat(),
        }, format="json")
        assert resp.status_code == 404


# ===========================================================================
# Webhook conversion
# ===========================================================================

@pytest.mark.django_db
class TestExtensionWebhookConversion:

    def _make_draft(self, client_profile, room, branch) -> ExtensionDraft:
        from django.utils import timezone
        booking = _make_paid_booking(client_profile, room, branch)
        return ExtensionDraft.objects.create(
            booking=booking,
            new_check_out_date=booking.check_out_date + timedelta(days=2),
            amount=Decimal(room.base_price) * 2,
            payment_intent_id="pi_ext_succeed",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_succeeded_extends_booking_and_creates_payment(
        self, client_profile, room, branch,
    ):
        draft = self._make_draft(client_profile, room, branch)
        original_co = draft.booking.check_out_date

        process_webhook_event(_succeeded_event("pi_ext_succeed"))

        draft.refresh_from_db()
        assert draft.status == ExtensionDraft.Status.SUCCEEDED

        draft.booking.refresh_from_db()
        assert draft.booking.check_out_date == original_co + timedelta(days=2)
        assert draft.booking.status == Booking.BookingStatus.PAID

        pmt = Payment.objects.get(payment_intent_id="pi_ext_succeed")
        assert pmt.is_paid is True
        assert pmt.booking == draft.booking

    @patch("apps.payments.stripe_service.stripe.Refund.create")
    def test_race_loser_is_refunded(
        self, mock_refund, client_profile, room, branch, db,
    ):
        """Another booking grabbed the extension window → refund (R1)."""
        from conftest import ClientFactory
        draft = self._make_draft(client_profile, room, branch)

        # Race winner: a different client's booking now overlaps the extension.
        other_client = ClientFactory()
        Booking.objects.create(
            client=other_client, room=room, branch=branch,
            check_in_date=draft.booking.check_out_date,
            check_out_date=draft.new_check_out_date,
            price_at_booking=Decimal("1"), discount_amount=Decimal("0"),
            final_price=Decimal("1"),
            status=Booking.BookingStatus.PAID,
        )

        process_webhook_event(_succeeded_event("pi_ext_succeed"))

        draft.refresh_from_db()
        assert draft.status == ExtensionDraft.Status.FAILED
        assert draft.failure_reason == "race_lost_overlap"
        mock_refund.assert_called_once_with(
            payment_intent="pi_ext_succeed", reason="requested_by_customer",
        )
        # Original booking unchanged.
        draft.booking.refresh_from_db()
        assert draft.booking.check_out_date == draft.new_check_out_date - timedelta(days=2)


# ===========================================================================
# Polling endpoint detects extension drafts
# ===========================================================================

@pytest.mark.django_db
class TestPollingExtensionDraft:

    def test_returns_kind_extension(self, client_profile, room, branch):
        from django.utils import timezone
        booking = _make_paid_booking(client_profile, room, branch)
        draft = ExtensionDraft.objects.create(
            booking=booking,
            new_check_out_date=booking.check_out_date + timedelta(days=1),
            amount=Decimal("100000"),
            payment_intent_id="pi_ext_poll",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        resp = _auth(client_profile).get(f"/api/v1/payments/drafts/{draft.id}/")
        assert resp.status_code == 200
        assert resp.data["kind"] == "extension"
        assert resp.data["status"] == "pending"
        assert resp.data["booking_id"] == booking.pk
