"""
Stripe service layer — wrapper around stripe-python library.

Handles:
- PaymentIntent creation
- Webhook event verification
- Draft booking/extension payment management
"""

import logging
import stripe
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


def construct_webhook_event(payload, sig_header, endpoint_secret):
    """
    Verify and construct a Stripe webhook event.

    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
        endpoint_secret: Stripe endpoint secret for webhook verification

    Returns:
        The verified event dict

    Raises:
        stripe.error.InvalidSignatureError: If signature is invalid
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        return event
    except ValueError:
        raise stripe.error.InvalidSignatureError(
            "Payload is not valid JSON", sig_header
        )
    except stripe.error.SignatureVerificationError:
        raise


def process_webhook_event(event):
    """
    Process a verified Stripe webhook event.

    Handles:
    - payment_intent.succeeded
    - payment_intent.payment_failed
    - payment_intent.canceled

    The event may be a dict or a MagicMock/object with .type and .data attributes.

    Args:
        event: The webhook event from Stripe (dict or mock object)

    Returns:
        None
    """
    # Support both dict-style (from tasks) and mock-style objects (from tests)
    if isinstance(event, dict):
        event_type = event.get("type")
        event_id = event.get("id", "")
        data_obj = event.get("data", {})
        if isinstance(data_obj, dict):
            payment_intent_data = data_obj.get("object", {})
        else:
            payment_intent_data = getattr(data_obj, "object", {})
    else:
        event_type = getattr(event, "type", None)
        event_id = getattr(event, "id", "")
        data_obj = getattr(event, "data", None)
        payment_intent_data = getattr(data_obj, "object", {}) if data_obj else {}

    if not payment_intent_data:
        return

    if isinstance(payment_intent_data, dict):
        intent_id = payment_intent_data.get("id")
    else:
        intent_id = getattr(payment_intent_data, "id", None)

    if not intent_id:
        return

    if event_type == "payment_intent.succeeded":
        _handle_succeeded(event_id, intent_id, payment_intent_data)
    elif event_type == "payment_intent.payment_failed":
        _handle_failed(event_id, intent_id, payment_intent_data)
    elif event_type == "payment_intent.canceled":
        _handle_canceled(event_id, intent_id)


@transaction.atomic
def _handle_succeeded(event_id: str, intent_id: str, payment_intent_data: dict):
    """Convert a BookingDraft or ExtensionDraft to a real booking/payment."""
    from apps.payments.models import BookingDraft, ExtensionDraft, Payment, ProcessedStripeEvent
    from apps.bookings.models import Booking
    from apps.bookings.services import create_booking

    # Idempotency — if we already processed this event, skip
    if event_id and ProcessedStripeEvent.objects.filter(event_id=event_id).exists():
        logger.info("Duplicate Stripe event %s — skipping", event_id)
        return

    if event_id:
        ProcessedStripeEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_type": "payment_intent.succeeded"},
        )

    # Try booking draft first
    try:
        draft = BookingDraft.objects.select_for_update().get(
            payment_intent_id=intent_id,
            status=BookingDraft.Status.PENDING,
        )
    except BookingDraft.DoesNotExist:
        draft = None

    if draft:
        # Race-loser check: see if an overlapping paid booking already exists
        overlap = Booking.objects.filter(
            room=draft.room,
            status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
            check_in_date__lt=draft.check_out_date,
            check_out_date__gt=draft.check_in_date,
        ).exists()
        if overlap:
            draft.status = BookingDraft.Status.FAILED
            draft.failure_reason = "race_lost_overlap"
            draft.save(update_fields=["status", "failure_reason", "updated_at"])
            try:
                stripe.Refund.create(
                    payment_intent=intent_id,
                    reason="requested_by_customer",
                )
            except Exception:
                logger.exception("Stripe refund failed for %s", intent_id)
            return

        # Create the booking
        booking = create_booking(
            client=draft.client,
            room=draft.room,
            branch=draft.branch,
            check_in_date=draft.check_in_date,
            check_out_date=draft.check_out_date,
            price_at_booking=draft.amount,
            source="telegram",
        )
        booking.status = Booking.BookingStatus.PAID
        booking.save(update_fields=["status"])

        Payment.objects.create(
            booking=booking,
            amount=draft.amount,
            payment_type=Payment.PaymentType.ONLINE,
            is_paid=True,
            payment_intent_id=intent_id,
            stripe_event_id=event_id,
        )

        draft.status = BookingDraft.Status.SUCCEEDED
        draft.booking = booking
        draft.save(update_fields=["status", "booking", "updated_at"])
        return

    # Try extension draft
    try:
        ext_draft = ExtensionDraft.objects.select_for_update().get(
            payment_intent_id=intent_id,
            status=ExtensionDraft.Status.PENDING,
        )
    except ExtensionDraft.DoesNotExist:
        ext_draft = None

    if ext_draft:
        booking = ext_draft.booking
        # Race-loser check for extension
        overlap = Booking.objects.filter(
            room=booking.room,
            status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
            check_in_date__lt=ext_draft.new_check_out_date,
            check_out_date__gt=booking.check_out_date,
        ).exclude(pk=booking.pk).exists()
        if overlap:
            ext_draft.status = ExtensionDraft.Status.FAILED
            ext_draft.failure_reason = "race_lost_overlap"
            ext_draft.save(update_fields=["status", "failure_reason", "updated_at"])
            try:
                stripe.Refund.create(
                    payment_intent=intent_id,
                    reason="requested_by_customer",
                )
            except Exception:
                logger.exception("Stripe refund failed for %s", intent_id)
            return

        # Extend the booking
        booking.check_out_date = ext_draft.new_check_out_date
        booking.save(update_fields=["check_out_date"])

        Payment.objects.create(
            booking=booking,
            amount=ext_draft.amount,
            payment_type=Payment.PaymentType.ONLINE,
            is_paid=True,
            payment_intent_id=intent_id,
            stripe_event_id=event_id,
        )

        ext_draft.status = ExtensionDraft.Status.SUCCEEDED
        ext_draft.save(update_fields=["status", "updated_at"])


@transaction.atomic
def _handle_failed(event_id: str, intent_id: str, payment_intent_data: dict):
    """Mark draft as failed when payment fails."""
    from apps.payments.models import BookingDraft, ExtensionDraft

    if isinstance(payment_intent_data, dict):
        last_error = payment_intent_data.get("last_payment_error", {})
        reason = last_error.get("message", "payment_failed") if last_error else "payment_failed"
    else:
        reason = "payment_failed"

    for Model in (BookingDraft, ExtensionDraft):
        try:
            draft = Model.objects.get(payment_intent_id=intent_id, status=Model.Status.PENDING)
            draft.status = Model.Status.FAILED
            draft.failure_reason = reason
            draft.save(update_fields=["status", "failure_reason", "updated_at"])
        except Model.DoesNotExist:
            pass


def _handle_canceled(event_id: str, intent_id: str):
    """Mark draft as canceled."""
    from apps.payments.models import BookingDraft, ExtensionDraft

    for Model in (BookingDraft, ExtensionDraft):
        try:
            draft = Model.objects.get(payment_intent_id=intent_id, status=Model.Status.PENDING)
            draft.status = Model.Status.CANCELED
            draft.failure_reason = "stripe_canceled"
            draft.save(update_fields=["status", "failure_reason", "updated_at"])
        except Model.DoesNotExist:
            pass
