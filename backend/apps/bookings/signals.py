"""
Booking real-time hooks (Django signals).

These ``post_save`` receivers fire on every ``Booking`` save and serve
as the integration point for real-time systems (WebSocket, Telegram).

Step 13 — prepare only.  Actual WebSocket / Telegram dispatch will be
wired in a later step.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def on_booking_saved(sender, instance, created, **kwargs):
    """
    Fires after every ``Booking.save()``.

    Integration points (uncomment when ready):
        - WebSocket: emit ``booking.created`` / ``booking.updated``
          to the branch channel group.
        - Telegram: push notification to the admin on duty.
    """
    event = "booking.created" if created else "booking.updated"

    logger.info(
        "Signal [%s]: Booking #%s (status=%s, branch=%s)",
        event,
        instance.pk,
        instance.status,
        instance.branch_id,
    )

    # === WebSocket integration point ===
    # from channels.layers import get_channel_layer
    # from asgiref.sync import async_to_sync
    # channel_layer = get_channel_layer()
    # async_to_sync(channel_layer.group_send)(
    #     f"branch_{instance.branch_id}",
    #     {
    #         "type": "booking.event",
    #         "event": event,
    #         "booking_id": instance.pk,
    #         "status": instance.status,
    #     },
    # )

    # === Telegram integration point ===
    # from apps.integrations.telegram import send_booking_alert
    # send_booking_alert(instance, event)
