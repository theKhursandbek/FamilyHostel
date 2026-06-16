"""
Booking real-time hooks (Django signals).

These ``pre_save`` / ``post_save`` receivers fire on every ``Booking`` save
and serve as the integration point for real-time systems (WebSocket, Telegram).

Telegram integration:
    - On ``booking.created``          → notify administrators/directors at branch.
    - On status → ``paid``            → notify the client (booking confirmed).
    - On status → ``canceled``        → notify the client.
    - On status → ``completed``       → notify the client (checkout done).
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)

# Attribute name used to stash the previous status on the instance
# between pre_save and post_save without touching the DB.
_PREV_STATUS_ATTR = "_pre_save_status"


@receiver(pre_save, sender=Booking)
def on_booking_pre_save(sender, instance, **kwargs):
    """
    Snapshot the current DB status before the save so post_save can
    detect transitions without an extra SELECT.
    """
    if instance.pk:
        try:
            prev = Booking.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
            setattr(instance, _PREV_STATUS_ATTR, prev)
        except Exception:
            setattr(instance, _PREV_STATUS_ATTR, None)
    else:
        # New record — no previous status.
        setattr(instance, _PREV_STATUS_ATTR, None)


@receiver(post_save, sender=Booking)
def on_booking_saved(sender, instance, created, **kwargs):
    """
    Fires after every ``Booking.save()``.

    Telegram notifications:
        - Booking created → admin + director at the booking's branch.
        - Status transitions → client.
    """
    event = "booking.created" if created else "booking.updated"
    prev_status = getattr(instance, _PREV_STATUS_ATTR, None)
    new_status = instance.status

    logger.info(
        "Signal [%s]: Booking #%s (status=%s→%s, branch=%s)",
        event,
        instance.pk,
        prev_status,
        new_status,
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

    # === Telegram: client notifications on status transitions ===
    # We only fire when the status actually changed to avoid sending
    # duplicate messages on unrelated saves (e.g. room_id update).
    if not created and prev_status != new_status:
        _notify_client_on_transition(instance, prev_status=prev_status, new_status=new_status)

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


def _notify_client_on_transition(instance, *, prev_status: str | None, new_status: str) -> None:
    """Fire the appropriate client Telegram notification for a status change."""
    from apps.bookings.notifications import (
        notify_client_booking_canceled,
        notify_client_booking_completed,
        notify_client_booking_confirmed,
    )

    try:
        if new_status == Booking.BookingStatus.PAID:
            notify_client_booking_confirmed(instance)

        elif new_status == Booking.BookingStatus.CANCELED:
            was_paid = prev_status == Booking.BookingStatus.PAID
            notify_client_booking_canceled(instance, was_paid=was_paid)

        elif new_status == "completed":
            notify_client_booking_completed(instance)

    except Exception:
        logger.exception(
            "Failed to send client notification for Booking #%s "
            "on transition %s → %s",
            instance.pk,
            prev_status,
            new_status,
        )
