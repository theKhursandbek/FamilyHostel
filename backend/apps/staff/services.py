"""
Shift & Attendance business logic (README Section 7 & 14.6).

Rules:
    Attendance:
        - Late if check-in > 30 minutes past shift start
        - Absent if no check-in at all
        - No double check-in on the same date + shift
    Shifts:
        - One admin per shift per branch (also enforced by DB constraint)
    Salary Prep:
        - Count shifts per account in a date range
        - Count completed cleaning tasks per staff in a date range
"""

from __future__ import annotations

import datetime
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.cleaning.models import CleaningTask
from apps.reports.services import log_action, notify_roles, send_notification
from apps.staff.models import Attendance, ShiftAssignment

__all__ = [
    "check_in",
    "check_out",
    "mark_absent",
    "create_shift_assignment",
    "get_salary_summary",
]


# ==============================================================================
# SHIFT START TIMES (README Section 3.3 & 3.4)
# ==============================================================================

SHIFT_START_TIMES: dict[str, datetime.time] = {
    "day": datetime.time(8, 0),    # 08:00
    "night": datetime.time(19, 0),  # 19:00 (admin) / 18:00 (staff) — use 19:00 as threshold
}

LATE_THRESHOLD = timedelta(minutes=30)


# ==============================================================================
# ATTENDANCE
# ==============================================================================


@transaction.atomic
def check_in(
    *,
    account,
    branch,
    date,
    shift_type: str,
) -> Attendance:
    """
    Record staff/admin check-in. Determines on-time vs late.

    Rules:
        - Cannot check in twice for the same date + shift
        - Late if > 30 minutes after shift start time

    Returns:
        The ``Attendance`` record.

    Raises:
        ``ValidationError`` on double check-in.
    """
    # Prevent double check-in
    existing = Attendance.objects.filter(
        account=account,
        date=date,
        shift_type=shift_type,
    ).first()

    if existing and existing.check_in is not None:
        raise ValidationError(
            {"check_in": "Already checked in for this date and shift."}
        )

    now = timezone.now()

    # Determine late status
    shift_start = SHIFT_START_TIMES.get(shift_type, datetime.time(8, 0))
    shift_start_dt = timezone.make_aware(
        datetime.datetime.combine(date, shift_start),
        timezone=timezone.get_current_timezone(),
    )
    is_late = now > (shift_start_dt + LATE_THRESHOLD)
    status = (
        Attendance.AttendanceStatus.LATE
        if is_late
        else Attendance.AttendanceStatus.PRESENT
    )

    if existing:
        # Update an absence record that was pre-created
        existing.check_in = now
        existing.status = status
        existing.save(update_fields=["check_in", "status", "updated_at"])
        attendance = existing
    else:
        attendance = Attendance.objects.create(
            account=account,
            branch=branch,
            date=date,
            shift_type=shift_type,
            check_in=now,
            status=status,
        )

    # --- Audit ---
    log_action(
        account=account,
        action="attendance.check_in",
        entity_type="Attendance",
        entity_id=attendance.pk,
        after_data=_attendance_snapshot(attendance),
    )

    # --- Notification: late check-in → directors ---
    if is_late:
        notify_roles(
            roles=["director"],
            branch=branch,
            notification_type="shift",
            message=f"{account} checked in late for {shift_type} shift on {date}.",
        )

    return attendance


@transaction.atomic
def check_out(attendance: Attendance) -> Attendance:
    """Record check-out time on an existing attendance record."""
    if attendance.check_in is None:
        raise ValidationError(
            {"check_out": "Cannot check out without checking in first."}
        )
    if attendance.check_out is not None:
        raise ValidationError(
            {"check_out": "Already checked out."}
        )

    before = _attendance_snapshot(attendance)

    attendance.check_out = timezone.now()
    attendance.save(update_fields=["check_out", "updated_at"])

    # --- Audit ---
    log_action(
        account=attendance.account,
        action="attendance.check_out",
        entity_type="Attendance",
        entity_id=attendance.pk,
        before_data=before,
        after_data=_attendance_snapshot(attendance),
    )

    return attendance


def mark_absent(*, account, branch, date, shift_type: str) -> Attendance:
    """
    Mark a staff member as absent (called by scheduled job / manual).

    Creates an attendance record with status = absent and no check-in time.
    """
    attendance, created = Attendance.objects.get_or_create(
        account=account,
        date=date,
        shift_type=shift_type,
        defaults={
            "branch": branch,
            "status": Attendance.AttendanceStatus.ABSENT,
        },
    )
    if not created and attendance.check_in is None:
        # Already marked absent — no-op
        pass
    return attendance


# ==============================================================================
# SHIFT ASSIGNMENTS
# ==============================================================================


@transaction.atomic
def create_shift_assignment(
    *,
    account,
    role: str,
    branch,
    shift_type: str,
    date,
    assigned_by,
) -> ShiftAssignment:
    """
    Create a shift assignment with one-admin-per-shift validation.

    The DB UniqueConstraint also enforces this, but we check for a
    friendlier error message.
    """
    if role == ShiftAssignment.Role.ADMIN:
        conflict = ShiftAssignment.objects.filter(
            branch=branch,
            shift_type=shift_type,
            date=date,
            role=ShiftAssignment.Role.ADMIN,
        ).exists()
        if conflict:
            raise ValidationError(
                {"shift_type": "An admin is already assigned to this shift for this branch."}
            )

    assignment = ShiftAssignment.objects.create(
        account=account,
        role=role,
        branch=branch,
        shift_type=shift_type,
        date=date,
        assigned_by=assigned_by,
    )

    # --- Audit ---
    log_action(
        account=assigned_by.account if hasattr(assigned_by, "account") else None,
        action="shift.assigned",
        entity_type="ShiftAssignment",
        entity_id=assignment.pk,
        after_data={
            "id": assignment.pk,
            "account_id": account.pk,
            "role": role,
            "branch_id": branch.pk,
            "shift_type": shift_type,
            "date": str(date),
        },
    )

    # --- Notification: inform the assigned account ---
    send_notification(
        account_id=account.pk,
        notification_type="shift",
        message=f"You have been assigned a {shift_type} shift on {date} "
                f"at {branch} (role: {role}).",
    )

    return assignment


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _attendance_snapshot(attendance: Attendance) -> dict:
    """Return a JSON-serialisable dict of attendance state."""
    return {
        "id": attendance.pk,
        "account_id": attendance.account_id,
        "branch_id": attendance.branch_id,
        "date": str(attendance.date),
        "shift_type": attendance.shift_type,
        "check_in": str(attendance.check_in) if attendance.check_in else None,
        "check_out": str(attendance.check_out) if attendance.check_out else None,
        "status": attendance.status,
    }


# ==============================================================================
# SALARY PREPARATION (basic counters — full engine is a later step)
# ==============================================================================


def get_salary_summary(
    *,
    account,
    period_start,
    period_end,
) -> dict:
    """
    Get basic salary data for an account within a date range.

    Returns a dict with:
        - ``shift_count``: total shifts worked
        - ``days_present``: attendance records where status != absent
        - ``days_late``: attendance records with status = late
        - ``days_absent``: attendance records with status = absent
        - ``cleaning_tasks_completed``: completed tasks (if staff)
    """
    attendance_qs = Attendance.objects.filter(
        account=account,
        date__gte=period_start,
        date__lte=period_end,
    )

    stats = attendance_qs.aggregate(
        days_present=Count("pk", filter=Q(status="present")),
        days_late=Count("pk", filter=Q(status="late")),
        days_absent=Count("pk", filter=Q(status="absent")),
    )

    shift_count = ShiftAssignment.objects.filter(
        account=account,
        date__gte=period_start,
        date__lte=period_end,
    ).count()

    # Cleaning tasks (staff only — uses staff_profile relation)
    cleaning_count = 0
    staff_profile = getattr(account, "staff_profile", None)
    if staff_profile:
        cleaning_count = CleaningTask.objects.filter(
            assigned_to=staff_profile,
            status=CleaningTask.TaskStatus.COMPLETED,
            completed_at__date__gte=period_start,
            completed_at__date__lte=period_end,
        ).count()

    return {
        "shift_count": shift_count,
        "days_present": stats["days_present"],
        "days_late": stats["days_late"],
        "days_absent": stats["days_absent"],
        "cleaning_tasks_completed": cleaning_count,
    }
