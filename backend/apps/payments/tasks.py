"""
Payments Celery tasks — async operations for payment processing.

Tasks:
    - reap_stale_drafts: Clean up expired booking drafts (every 2 minutes)
    - process_payment_event_task: Process Stripe webhook events asynchronously
"""

from __future__ import annotations

import logging
import stripe
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="payments.reap_stale_drafts")
def reap_stale_drafts() -> dict:
    """
    Cancel expired booking and extension drafts.

    Scheduled every 2 minutes via CELERY_BEAT_SCHEDULE.
    BookingDrafts expire 5 minutes after creation if not confirmed.

    Returns:
        dict with counts: {"booking": N, "extension": M}
    """
    from .models import BookingDraft, ExtensionDraft

    now = timezone.now()
    booking_count = 0
    extension_count = 0

    # Reap expired booking drafts
    expired_booking = BookingDraft.objects.filter(
        expires_at__lte=now, status=BookingDraft.Status.PENDING,
    )
    for draft in expired_booking:
        try:
            stripe.PaymentIntent.cancel(draft.payment_intent_id)
        except Exception:
            logger.exception("Failed to cancel Stripe intent %s", draft.payment_intent_id)
        draft.status = BookingDraft.Status.CANCELED
        draft.failure_reason = "expired"
        draft.save(update_fields=["status", "failure_reason", "updated_at"])
        booking_count += 1

    # Reap expired extension drafts
    expired_extension = ExtensionDraft.objects.filter(
        expires_at__lte=now, status=ExtensionDraft.Status.PENDING,
    )
    for draft in expired_extension:
        try:
            stripe.PaymentIntent.cancel(draft.payment_intent_id)
        except Exception:
            logger.exception("Failed to cancel Stripe intent %s", draft.payment_intent_id)
        draft.status = ExtensionDraft.Status.CANCELED
        draft.failure_reason = "expired"
        draft.save(update_fields=["status", "failure_reason", "updated_at"])
        extension_count += 1

    logger.info("Reaped %d booking drafts, %d extension drafts", booking_count, extension_count)
    return {"booking": booking_count, "extension": extension_count}


@shared_task(name="payments.process_payment_event")
def process_payment_event_task(event_id: str, event_type: str, event_data: dict) -> bool:
    """
    Process a Stripe webhook event asynchronously.

    Called by the webhook handler to defer processing and ensure fast 200
    response time back to Stripe.

    Args:
        event_id: The Stripe event ID (evt_...)
        event_type: The Stripe event type (e.g., "payment_intent.succeeded")
        event_data: The event data dict

    Returns:
        True if newly processed, False if duplicate
    """
    from .models import ProcessedStripeEvent, Payment

    # Idempotency check
    if ProcessedStripeEvent.objects.filter(event_id=event_id).exists():
        logger.info("Duplicate Stripe event %s — skipping", event_id)
        return False

    ProcessedStripeEvent.objects.create(event_id=event_id, event_type=event_type)

    from .stripe_service import process_webhook_event
    try:
        process_webhook_event({"type": event_type, "data": event_data, "id": event_id})

        # Also mark any existing Payment row as paid when succeeded
        if event_type == "payment_intent.succeeded":
            intent_id = None
            if isinstance(event_data, dict):
                obj = event_data.get("object", {})
                if isinstance(obj, dict):
                    intent_id = obj.get("id")
            if intent_id:
                Payment.objects.filter(
                    payment_intent_id=intent_id, is_paid=False,
                ).update(is_paid=True)

        logger.info("Processed Stripe event: %s (%s)", event_id, event_type)
        return True
    except Exception as exc:
        logger.exception("Failed to process Stripe event %s: %s", event_type, exc)
        raise
