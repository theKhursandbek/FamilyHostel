"""Bookings Celery tasks (Section 14.4 — automatic checkout)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import Booking
from .services import complete_booking

logger = logging.getLogger(__name__)


@shared_task(name="bookings.auto_complete_due_bookings")
def auto_complete_due_bookings() -> int:
    """
    Auto-complete every paid booking whose check-out date is today or earlier.

    Scheduled daily at 12:00 (see ``CELERY_BEAT_SCHEDULE``). Runs idempotently:
    bookings that are already in ``completed``/``canceled`` are skipped because
    we filter on ``status=PAID``.

    Returns the number of bookings completed (useful for logging/tests).
    """
    today = timezone.localdate()
    qs = (
        Booking.objects
        .filter(status=Booking.BookingStatus.PAID, check_out_date__lte=today)
        .select_related("room", "branch")
    )

    completed = 0
    for booking in qs:
        try:
            complete_booking(booking, performed_by=None)
            completed += 1
        except Exception:  # pragma: no cover — defensive: never let one row break the run
            logger.exception("auto-complete failed for booking #%s", booking.pk)

    if completed:
        logger.info("auto_complete_due_bookings: completed %d booking(s)", completed)
    return completed
