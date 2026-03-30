"""
Cleaning real-time hooks (Django signals).

``post_save`` receiver on ``CleaningTask`` — integration point for
WebSocket / Telegram real-time notifications.

Step 13 — prepare only.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.cleaning.models import CleaningTask

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CleaningTask)
def on_cleaning_task_saved(sender, instance, created, **kwargs):
    """
    Fires after every ``CleaningTask.save()``.

    Integration points (uncomment when ready):
        - WebSocket: emit task status changes to the branch channel.
        - Telegram: notify assigned staff or director on task updates.
    """
    event = "cleaning_task.created" if created else "cleaning_task.updated"

    logger.info(
        "Signal [%s]: CleaningTask #%s (status=%s, room=%s, branch=%s)",
        event,
        instance.pk,
        instance.status,
        instance.room_id,
        instance.branch_id,
    )

    # === WebSocket integration point ===
    # from channels.layers import get_channel_layer
    # from asgiref.sync import async_to_sync
    # channel_layer = get_channel_layer()
    # async_to_sync(channel_layer.group_send)(
    #     f"branch_{instance.branch_id}",
    #     {
    #         "type": "cleaning.event",
    #         "event": event,
    #         "task_id": instance.pk,
    #         "status": instance.status,
    #         "room_id": instance.room_id,
    #     },
    # )

    # === Telegram integration point ===
    # from apps.integrations.telegram import send_cleaning_alert
    # send_cleaning_alert(instance, event)
