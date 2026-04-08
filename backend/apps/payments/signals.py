"""
Payment real-time hooks (Django signals).

``post_save`` receiver on ``Payment`` — integration point for
WebSocket / Telegram real-time notifications.

Telegram integration (Step 16 — README Section 26.4):
    - On ``payment.created`` where ``is_paid=True`` → notify admin + director.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payments.models import Payment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def on_payment_saved(sender, instance, created, **kwargs):
    """
    Fires after every ``Payment.save()``.

    Telegram notifications:
        - Payment created & paid → admin + director at the booking's branch.
    """
    if not created:
        return  # Payments are typically immutable after creation

    logger.info(
        "Signal [payment.created]: Payment #%s for Booking #%s "
        "(amount=%s, is_paid=%s)",
        instance.pk,
        instance.booking_id,
        instance.amount,
        instance.is_paid,
    )

    # === Telegram: paid payment → notify branch admins & directors ===
    if instance.is_paid:
        try:
            from apps.reports.services import notify_roles

            booking = instance.booking
            notify_roles(
                roles=["administrator", "director"],
                branch=booking.branch,
                notification_type="payment",
                message=(
                    f"\u2705 Payment #{instance.pk} received "
                    f"for booking #{booking.pk} "
                    f"(amount: {instance.amount} UZS, type: {instance.payment_type})."
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send payment.created notification for Payment #%s",
                instance.pk,
            )

    # === WebSocket: broadcast payment event to dashboards (Step 21.4) ===
    try:
        from config.ws_events import send_dashboard_event

        booking = instance.booking
        send_dashboard_event(
            event_type="payment.completed" if instance.is_paid else "payment.created",
            data={
                "payment_id": instance.pk,
                "booking_id": instance.booking_id,
                "amount": str(instance.amount),
                "is_paid": instance.is_paid,
                "payment_type": instance.payment_type,
            },
            branch_id=booking.branch_id,
        )
    except Exception:
        logger.exception(
            "Failed to send WS event for Payment #%s", instance.pk,
        )
