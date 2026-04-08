"""
Booking real-time hooks (Django signals).

These ``post_save`` receivers fire on every ``Booking`` save and serve
as the integration point for real-time systems (WebSocket, Telegram).

Telegram integration (Step 16 — README Section 26.4):
    - On ``booking.created`` → notify administrators/directors at the branch.
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

    Telegram notifications:
        - Booking created → admin + director at the booking's branch.
    """
    event = "booking.created" if created else "booking.updated"

    logger.info(
        "Signal [%s]: Booking #%s (status=%s, branch=%s)",
        event,
        instance.pk,
        instance.status,
        instance.branch_id,
    )

    # === Telegram: booking created → notify branch admins & directors ===
    if created:
        try:
            from apps.reports.services import notify_roles

            notify_roles(
                roles=["administrator", "director"],
                branch=instance.branch,
                notification_type="booking",
                message=(
                    f"\U0001f4cb New booking #{instance.pk} created "
                    f"(room {instance.room}, "
                    f"check-in: {instance.check_in_date}, "
                    f"check-out: {instance.check_out_date})."
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send booking.created notification for Booking #%s",
                instance.pk,
            )

    # === WebSocket: broadcast booking event to dashboards (Step 21.4) ===
    try:
        from config.ws_events import send_dashboard_event

        send_dashboard_event(
            event_type=event,
            data={
                "booking_id": instance.pk,
                "status": instance.status,
                "room_id": instance.room_id,
                "branch_id": instance.branch_id,
            },
            branch_id=instance.branch_id,
        )
    except Exception:
        logger.exception(
            "Failed to send WS event for Booking #%s", instance.pk,
        )
