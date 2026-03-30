"""
Unit tests — Stripe payment integration.

All Stripe API calls are mocked. Tests cover:
    - create_payment_intent (service)
    - Webhook signature verification
    - payment_intent.succeeded handler
    - payment_intent.payment_failed handler
    - Idempotency (duplicate event rejection)
    - Webhook view (HTTP-level)
"""

import hashlib
import hmac
import json
import time
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.bookings.models import Booking
from apps.payments.models import Payment, ProcessedStripeEvent
from apps.payments.stripe_service import (
    _handle_payment_failed,
    _handle_payment_succeeded,
    create_payment_intent,
    construct_webhook_event,
    process_webhook_event,
)
from apps.payments.views import StripeWebhookView

from conftest import BookingFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stripe_event(
    event_id="evt_test_123",
    event_type="payment_intent.succeeded",
    intent_id="pi_test_abc",
    amount=500000,
    failure_message=None,
) -> Any:
    """Build a mock Stripe Event object mimicking stripe.Event structure.

    Uses dicts for ``data.object`` (matching Stripe type stubs) and
    SimpleNamespace for the outer event envelope (attribute access on
    ``event.id``, ``event.type``, ``event.data``).
    """
    last_payment_error = None
    if failure_message:
        last_payment_error = {"message": failure_message}

    payment_intent = {
        "id": intent_id,
        "amount": amount,
        "currency": "uzs",
        "metadata": {"booking_id": "1"},
        "last_payment_error": last_payment_error,
    }

    event = SimpleNamespace(
        id=event_id,
        type=event_type,
        data=SimpleNamespace(object=payment_intent),
    )
    return event


def _generate_stripe_signature(payload: bytes, secret: str) -> str:
    """Generate a valid Stripe-Signature header value for testing."""
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


# ===========================================================================
# Service-level tests
# ===========================================================================


@pytest.mark.django_db
class TestCreatePaymentIntent:
    """Tests for create_payment_intent()."""

    @patch("apps.payments.stripe_service.stripe.PaymentIntent.create")
    def test_creates_intent_and_local_payment(self, mock_create, booking):
        mock_create.return_value = SimpleNamespace(id="pi_test_xyz")

        payment = create_payment_intent(booking=booking)

        assert payment.payment_intent_id == "pi_test_xyz"
        assert payment.payment_type == "online"
        assert payment.is_paid is False
        assert payment.amount == booking.final_price
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["currency"] == "uzs"
        assert call_kwargs["amount"] == int(booking.final_price)

    @patch("apps.payments.stripe_service.stripe.PaymentIntent.create")
    def test_returns_existing_pending_intent(self, mock_create, booking):
        """If a pending intent already exists, return it without calling Stripe."""
        mock_create.return_value = SimpleNamespace(id="pi_first")
        first = create_payment_intent(booking=booking)

        # Second call should NOT hit Stripe
        mock_create.reset_mock()
        second = create_payment_intent(booking=booking)

        assert second.pk == first.pk
        mock_create.assert_not_called()

    @patch("apps.payments.stripe_service.stripe.PaymentIntent.create")
    def test_rejects_non_pending_booking(self, mock_create, booking):
        booking.status = "paid"
        booking.save()

        with pytest.raises(Exception, match="Cannot create payment"):
            create_payment_intent(booking=booking)

        mock_create.assert_not_called()

    @patch("apps.payments.stripe_service.stripe.PaymentIntent.create")
    def test_rejects_already_paid_booking(self, mock_create, booking):
        # Simulate existing paid payment
        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="manual",
            is_paid=True,
        )

        with pytest.raises(Exception, match="already been paid"):
            create_payment_intent(booking=booking)

        mock_create.assert_not_called()


# ===========================================================================
# Webhook handler tests
# ===========================================================================


@pytest.mark.django_db
class TestHandlePaymentSucceeded:
    """Tests for _handle_payment_succeeded()."""

    def test_marks_payment_and_booking_paid(self, booking):
        # Create a pending online payment
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_success_1",
        )

        event = _make_stripe_event(
            event_id="evt_succ_1",
            event_type="payment_intent.succeeded",
            intent_id="pi_success_1",
        )

        _handle_payment_succeeded(event)

        payment.refresh_from_db()
        assert payment.is_paid is True
        assert payment.paid_at is not None
        assert payment.stripe_event_id == "evt_succ_1"

        booking.refresh_from_db()
        assert booking.status == "paid"

    def test_skips_already_paid_payment(self, booking):
        _payment = Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=True,
            payment_intent_id="pi_already_paid",
        )

        event = _make_stripe_event(
            intent_id="pi_already_paid",
        )

        # Should not raise, just skip
        _handle_payment_succeeded(event)

    def test_handles_unknown_intent_gracefully(self):
        event = _make_stripe_event(intent_id="pi_unknown_xyz")

        # Should not raise — just log warning
        _handle_payment_succeeded(event)


@pytest.mark.django_db
class TestHandlePaymentFailed:
    """Tests for _handle_payment_failed()."""

    def test_logs_failure_without_changing_status(self, booking):
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_fail_1",
        )

        event = _make_stripe_event(
            event_id="evt_fail_1",
            event_type="payment_intent.payment_failed",
            intent_id="pi_fail_1",
            failure_message="Card declined",
        )

        _handle_payment_failed(event)

        payment.refresh_from_db()
        assert payment.is_paid is False  # NOT changed

        booking.refresh_from_db()
        assert booking.status == "pending"  # NOT changed

    def test_handles_unknown_intent_gracefully(self):
        event = _make_stripe_event(
            event_type="payment_intent.payment_failed",
            intent_id="pi_unknown_fail",
            failure_message="Card declined",
        )

        # Should not raise
        _handle_payment_failed(event)


# ===========================================================================
# Idempotency tests
# ===========================================================================


@pytest.mark.django_db
class TestProcessWebhookEvent:
    """Tests for process_webhook_event() idempotency."""

    def test_first_event_is_processed(self, booking):
        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_idem_1",
        )

        event = _make_stripe_event(
            event_id="evt_idem_1",
            intent_id="pi_idem_1",
        )

        result = process_webhook_event(event)
        assert result is True
        assert ProcessedStripeEvent.objects.filter(event_id="evt_idem_1").exists()

    def test_duplicate_event_is_rejected(self, booking):
        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_idem_2",
        )

        event = _make_stripe_event(
            event_id="evt_idem_2",
            intent_id="pi_idem_2",
        )

        first = process_webhook_event(event)
        second = process_webhook_event(event)

        assert first is True
        assert second is False
        assert ProcessedStripeEvent.objects.filter(event_id="evt_idem_2").count() == 1

    def test_unhandled_event_type_still_recorded(self):
        event = _make_stripe_event(
            event_id="evt_unknown_type",
            event_type="charge.refunded",
        )

        result = process_webhook_event(event)
        assert result is True
        assert ProcessedStripeEvent.objects.filter(event_id="evt_unknown_type").exists()


# ===========================================================================
# Webhook view (HTTP-level) tests
# ===========================================================================


@pytest.mark.django_db
class TestStripeWebhookView:
    """Integration tests for the StripeWebhookView."""

    def test_missing_signature_returns_400(self, client):
        url = reverse("payments:stripe-webhook")
        resp = client.post(
            url,
            data=b'{"type":"test"}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Missing" in resp.json()["error"]

    @patch("apps.payments.views.construct_webhook_event")
    def test_invalid_signature_returns_400(self, mock_construct, client):
        from stripe import SignatureVerificationError
        mock_construct.side_effect = SignatureVerificationError(
            "bad sig", "sig_header",
        )

        url = reverse("payments:stripe-webhook")
        resp = client.post(
            url,
            data=b'{"type":"test"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=bad",
        )
        assert resp.status_code == 400
        assert "Invalid signature" in resp.json()["error"]

    @patch("apps.payments.views.process_webhook_event")
    @patch("apps.payments.views.construct_webhook_event")
    def test_valid_webhook_returns_200(
        self, mock_construct, mock_process, client, booking,
    ):
        mock_event = _make_stripe_event()
        mock_construct.return_value = mock_event
        mock_process.return_value = True

        url = reverse("payments:stripe-webhook")
        resp = client.post(
            url,
            data=b'{"type":"payment_intent.succeeded"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["new"] is True
        mock_process.assert_called_once_with(mock_event)

    @patch("apps.payments.views.process_webhook_event")
    @patch("apps.payments.views.construct_webhook_event")
    def test_duplicate_webhook_returns_200_with_new_false(
        self, mock_construct, mock_process, client,
    ):
        mock_event = _make_stripe_event(event_id="evt_dup")
        mock_construct.return_value = mock_event
        mock_process.return_value = False

        url = reverse("payments:stripe-webhook")
        resp = client.post(
            url,
            data=b'{"type":"payment_intent.succeeded"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
        )
        assert resp.status_code == 200
        assert resp.json()["new"] is False
