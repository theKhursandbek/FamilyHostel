"""
Payment real-time hooks (Django signals).

``post_save`` receiver on ``Payment`` — integration point for
WebSocket / Telegram real-time notifications.

Step 13 — prepare only.
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

    Integration points (uncomment when ready):
        - WebSocket: emit ``payment.created`` to the branch channel.
        - Telegram: push payment confirmation to the admin on duty.
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

    # === WebSocket integration point ===
    # from channels.layers import get_channel_layer
    # from asgiref.sync import async_to_sync
    # branch_id = instance.booking.branch_id
    # channel_layer = get_channel_layer()
    # async_to_sync(channel_layer.group_send)(
    #     f"branch_{branch_id}",
    #     {
    #         "type": "payment.event",
    #         "event": "payment.created",
    #         "payment_id": instance.pk,
    #         "booking_id": instance.booking_id,
    #         "amount": str(instance.amount),
    #     },
    # )

    # === Telegram integration point ===
    # from apps.integrations.telegram import send_payment_alert
    # send_payment_alert(instance)
