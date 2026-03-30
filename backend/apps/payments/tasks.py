"""
Celery tasks — Payment processing (Step 17).

Offloads Stripe webhook event processing to a background worker
for better HTTP response times on the webhook endpoint.

Tasks:
    - ``process_payment_event_task`` — process a Stripe webhook event payload
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="payments.process_payment_event",
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    acks_late=True,
)
def process_payment_event_task(
    self,
    event_id: str,
    event_type: str,
    event_data: dict,
) -> bool:
    """
    Process a Stripe webhook event in the background.

    Args:
        event_id: Stripe event ID (``evt_...``).
        event_type: Event type string (``payment_intent.succeeded`` etc.).
        event_data: The ``event.data`` dict from Stripe.

    Returns:
        ``True`` if the event was processed for the first time.
        ``False`` if it was a duplicate.
    """
    from types import SimpleNamespace

    from apps.payments.stripe_service import process_webhook_event

    # Reconstruct a minimal event-like object that process_webhook_event expects
    event = SimpleNamespace(
        id=event_id,
        type=event_type,
        data=SimpleNamespace(object=event_data.get("object", {})),
    )

    return process_webhook_event(event)  # type: ignore[arg-type]
