"""
Reporting Service — aggregated branch reports (README Section 26.3 & Step 19).

All functions accept ``branch_id`` and a date range (``date_from``, ``date_to``)
and return plain dicts (or lists of dicts) suitable for JSON serialisation or
CSV export.

Functions
---------
- ``get_total_revenue``     — SUM(final_price WHERE status='paid')
- ``get_booking_stats``     — COUNT bookings grouped by status
- ``get_staff_performance`` — COUNT completed cleaning tasks per staff
- ``get_admin_income``      — SUM payments grouped by administrator
- ``get_attendance_report`` — COUNT present / late / absent per account
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.bookings.models import Booking
from apps.cleaning.models import CleaningTask
from apps.payments.models import Payment
from apps.staff.models import Attendance

__all__ = [
    "get_total_revenue",
    "get_booking_stats",
    "get_staff_performance",
    "get_admin_income",
    "get_attendance_report",
]


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------


def get_total_revenue(
    branch_id: int,
    date_from: datetime.date,
    date_to: datetime.date,
) -> dict[str, Any]:
    """
    Total revenue from **paid** bookings at *branch* whose ``check_in_date``
    falls within ``[date_from, date_to]``.

    Returns::

        {
            "branch_id": int,
            "date_from": date,
            "date_to": date,
            "total_revenue": Decimal,
            "booking_count": int,
        }
    """
    qs = Booking.objects.filter(
        branch_id=branch_id,
        status=Booking.BookingStatus.PAID,
        check_in_date__gte=date_from,
        check_in_date__lte=date_to,
    )

    agg = qs.aggregate(
        total_revenue=Coalesce(
            Sum("final_price"),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        booking_count=Count("pk"),
    )

    return {
        "branch_id": branch_id,
        "date_from": date_from,
        "date_to": date_to,
        "total_revenue": agg["total_revenue"],
        "booking_count": agg["booking_count"],
    }


# ---------------------------------------------------------------------------
# Booking statistics
# ---------------------------------------------------------------------------


def get_booking_stats(
    branch_id: int,
    date_from: datetime.date,
    date_to: datetime.date,
) -> dict[str, Any]:
    """
    Count bookings at *branch* grouped by status.

    Returns::

        {
            "branch_id": int,
            "date_from": date,
            "date_to": date,
            "total": int,
            "pending": int,
            "paid": int,
            "canceled": int,
        }
    """
    qs = Booking.objects.filter(
        branch_id=branch_id,
        check_in_date__gte=date_from,
        check_in_date__lte=date_to,
    )

    agg = qs.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=Booking.BookingStatus.PENDING)),
        paid=Count("pk", filter=Q(status=Booking.BookingStatus.PAID)),
        canceled=Count("pk", filter=Q(status=Booking.BookingStatus.CANCELED)),
    )

    return {
        "branch_id": branch_id,
        "date_from": date_from,
        "date_to": date_to,
        **agg,
    }


# ---------------------------------------------------------------------------
# Staff performance (cleaning tasks)
# ---------------------------------------------------------------------------


def get_staff_performance(
    branch_id: int,
    date_from: datetime.date,
    date_to: datetime.date,
) -> list[dict[str, Any]]:
    """
    Count **completed** cleaning tasks per staff member at *branch*.

    Returns a list sorted by ``completed_count`` descending::

        [
            {
                "staff_id": int,
                "staff_name": str,
                "completed_count": int,
            },
            ...
        ]
    """
    rows = (
        CleaningTask.objects.filter(
            branch_id=branch_id,
            status=CleaningTask.TaskStatus.COMPLETED,
            completed_at__date__gte=date_from,
            completed_at__date__lte=date_to,
            assigned_to__isnull=False,
        )
        .values("assigned_to__pk", "assigned_to__full_name")
        .annotate(completed_count=Count("pk"))
        .order_by("-completed_count")
    )

    return [
        {
            "staff_id": row["assigned_to__pk"],
            "staff_name": row["assigned_to__full_name"],
            "completed_count": row["completed_count"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Admin income (payments collected)
# ---------------------------------------------------------------------------


def get_admin_income(
    branch_id: int,
    date_from: datetime.date,
    date_to: datetime.date,
) -> list[dict[str, Any]]:
    """
    Sum of **paid** payment amounts grouped by the administrator who
    created the payment, for bookings at *branch* within the date range.

    Returns a list sorted by ``total_collected`` descending::

        [
            {
                "admin_id": int,
                "admin_name": str,
                "total_collected": Decimal,
                "payment_count": int,
            },
            ...
        ]
    """
    rows = (
        Payment.objects.filter(
            booking__branch_id=branch_id,
            is_paid=True,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            created_by__isnull=False,
        )
        .values("created_by__pk", "created_by__full_name")
        .annotate(
            total_collected=Coalesce(
                Sum("amount"),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            payment_count=Count("pk"),
        )
        .order_by("-total_collected")
    )

    return [
        {
            "admin_id": row["created_by__pk"],
            "admin_name": row["created_by__full_name"],
            "total_collected": row["total_collected"],
            "payment_count": row["payment_count"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Attendance report
# ---------------------------------------------------------------------------


def get_attendance_report(
    branch_id: int,
    date_from: datetime.date,
    date_to: datetime.date,
) -> list[dict[str, Any]]:
    """
    Count attendance records per account at *branch*, grouped by status.

    Returns a list sorted by ``total`` descending::

        [
            {
                "account_id": int,
                "present": int,
                "late": int,
                "absent": int,
                "total": int,
            },
            ...
        ]
    """
    rows = (
        Attendance.objects.filter(
            branch_id=branch_id,
            date__gte=date_from,
            date__lte=date_to,
        )
        .order_by()  # clear default ordering before values/annotate
        .values("account_id")
        .annotate(
            present=Count(
                "pk", filter=Q(status=Attendance.AttendanceStatus.PRESENT),
            ),
            late=Count(
                "pk", filter=Q(status=Attendance.AttendanceStatus.LATE),
            ),
            absent=Count(
                "pk", filter=Q(status=Attendance.AttendanceStatus.ABSENT),
            ),
            total=Count("pk"),
        )
        .order_by("-total")
    )

    return [
        {
            "account_id": row["account_id"],
            "present": row["present"],
            "late": row["late"],
            "absent": row["absent"],
            "total": row["total"],
        }
        for row in rows
    ]
