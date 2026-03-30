"""
Cleaning real-time hooks (Django signals).

``post_save`` receiver on ``CleaningTask`` — integration point for
WebSocket / Telegram real-time notifications.

Telegram integration (Step 16 — README Section 26.4):
    - On ``cleaning_task.updated`` with assigned staff → notify the staff member.
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

    Telegram notifications:
        - Task assigned (status == in_progress + assigned_to set) → notify staff.
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

    # === Telegram: task assigned → notify the assigned staff member ===
    if (
        not created
        and instance.status == CleaningTask.TaskStatus.IN_PROGRESS
        and instance.assigned_to_id
    ):
        try:
            from apps.reports.services import send_notification

            staff = instance.assigned_to
            send_notification(
                account_id=staff.account_id,
                notification_type="cleaning",
                message=(
                    f"\U0001f9f9 Cleaning task #{instance.pk} assigned to you "
                    f"(room {instance.room}, priority: {instance.priority})."
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send cleaning_task.assigned notification "
                "for CleaningTask #%s",
                instance.pk,
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
