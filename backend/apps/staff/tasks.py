"""
Staff-related Celery tasks.

Two scheduled jobs registered in ``CELERY_BEAT_SCHEDULE``:

* ``staff.detect_absences`` — once per day at 03:00. For yesterday's shift
  assignments with no Attendance row, creates an Absence Penalty and pings
  the staff member + their director.

* ``staff.shift_start_reminders`` — every 15 minutes. For shifts starting
  within the next ~30 minutes, sends a notification to the assignee.

Both tasks are idempotent (use natural keys to dedupe).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="staff.detect_absences")
def detect_absences() -> int:
    """Penalise staff who didn't check in for yesterday's shift."""
    from apps.reports.models import Penalty
    from apps.reports.services import send_notification
    from apps.staff.models import Attendance, ShiftAssignment

    yesterday = timezone.localdate() - timedelta(days=1)
    assignments = ShiftAssignment.objects.filter(date=yesterday).select_related("account")

    created = 0
    for assignment in assignments:
        had_attendance = Attendance.objects.filter(
            account_id=assignment.account_id,
            date=yesterday,
            shift_type=assignment.shift_type,
        ).exists()
        if had_attendance:
            continue

        # Idempotency key: type=absence + same day + same account.
        already = Penalty.objects.filter(
            account_id=assignment.account_id,
            type=Penalty.PenaltyType.ABSENCE,
            created_at__date=timezone.localdate(),
        ).exists()
        if already:
            continue

        Penalty.objects.create(
            account_id=assignment.account_id,
            type=Penalty.PenaltyType.ABSENCE,
            count=1,
            penalty_amount=Decimal("0"),
            reason=f"No check-in for {assignment.shift_type} shift on {yesterday}",
        )
        try:
            send_notification(
                assignment.account_id,
                "absence_penalty",
                f"You were marked absent for the {assignment.shift_type} shift on {yesterday}.",
            )
        except Exception:  # noqa: BLE001 — never crash the beat
            logger.exception("notify(absence) failed for account=%s", assignment.account_id)
        created += 1

    logger.info("detect_absences: %s penalties created for %s", created, yesterday)
    return created


@shared_task(name="staff.shift_start_reminders")
def shift_start_reminders() -> int:
    """Notify staff 30 minutes before their shift starts.

    Shift start times are derived from ``shift_type``:
        day   → 08:00 local
        night → 20:00 local
    """
    from apps.staff.models import ShiftAssignment
    from apps.reports.services import send_notification

    now = timezone.localtime()
    today = now.date()
    minute_window = (28, 33)  # +28..+33 minutes from now → ~30 min reminder

    sent = 0
    for assignment in ShiftAssignment.objects.filter(date=today):
        start_hour = 8 if assignment.shift_type == "day" else 20
        start_dt = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        delta_min = (start_dt - now).total_seconds() / 60
        if not (minute_window[0] <= delta_min <= minute_window[1]):
            continue

        # Per-shift dedupe via cache (15-min beat → at most one fires).
        from django.core.cache import cache
        key = f"staff:reminder:{assignment.id}:{today.isoformat()}"
        if cache.get(key):
            continue
        cache.set(key, True, timeout=3 * 3600)

        try:
            send_notification(
                assignment.account_id,
                "shift_reminder",
                f"Your {assignment.shift_type} shift starts at {start_hour:02d}:00.",
            )
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("notify(shift) failed for assignment=%s", assignment.id)

    logger.info("shift_start_reminders: sent %s reminders", sent)
    return sent
