"""
Attendance real-time hooks (Django signals) — Step 21.4.

``post_save`` receiver on ``Attendance`` — broadcasts WebSocket events
when attendance records are created or updated (check-in / check-out).
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.staff.models import Attendance

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Attendance)
def on_attendance_saved(sender, instance, created, **kwargs):
    """
    Fires after every ``Attendance.save()``.

    Broadcasts attendance events via WebSocket to dashboard consumers.
    """
    event = "attendance.created" if created else "attendance.updated"

    logger.info(
        "Signal [%s]: Attendance #%s (status=%s, account=%s, branch=%s)",
        event,
        instance.pk,
        instance.status,
        instance.account_id,
        instance.branch_id,
    )

    # === WebSocket: broadcast attendance event to dashboards ===
    try:
        from config.ws_events import send_dashboard_event

        send_dashboard_event(
            event_type=event,
            data={
                "attendance_id": instance.pk,
                "account_id": instance.account_id,
                "status": instance.status,
                "shift_type": instance.shift_type,
                "branch_id": instance.branch_id,
                "date": str(instance.date),
            },
            branch_id=instance.branch_id,
        )
    except Exception:
        logger.exception(
            "Failed to send WS event for Attendance #%s", instance.pk,
        )
