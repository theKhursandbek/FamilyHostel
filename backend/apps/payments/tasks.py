"""
Payments Celery tasks — async operations for payment processing.

Tasks:
    - reap_stale_drafts: Clean up expired booking drafts (every 2 minutes)
    - process_payment_event_task: Process Stripe webhook events asynchronously
"""

from __future__ import annotations

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="payments.reap_stale_drafts")
def reap_stale_drafts() -> int:
    """
    Delete expired booking drafts.

    Scheduled every 2 minutes via CELERY_BEAT_SCHEDULE.
    BookingDrafts expire 5 minutes after creation if not confirmed.

    Returns:
        The number of drafts deleted
    """
    from django.utils import timezone
    from .models import BookingDraft

    now = timezone.now()
    expired = BookingDraft.objects.filter(created_at__lt=now, status="pending")
    count, _ = expired.delete()
    logger.info(f"Reaped {count} stale booking drafts")
    return count


@shared_task(name="payments.process_payment_event_task")
def process_payment_event_task(event_type: str, event_data: dict) -> None:
    """
    Process a Stripe webhook event asynchronously.

    Called by the webhook handler to defer processing and ensure fast 200
    response time back to Stripe.

    Args:
        event_type: The Stripe event type (e.g., "payment_intent.succeeded")
        event_data: The event data dict

    Returns:
        None
    """
    from .stripe_service import process_webhook_event

    try:
        process_webhook_event({"type": event_type, "data": event_data})
        logger.info(f"Processed Stripe event: {event_type}")
    except Exception as exc:
        logger.exception(f"Failed to process Stripe event {event_type}: {exc}")
        raise
