"""
Monthly Report generation service (Step 21.7).

Aggregates branch data (revenue, bookings, attendance, penalties,
facility issues) for a given month/year and persists a MonthlyReport.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.accounts.models import Administrator, Staff
from apps.reports.models import FacilityLog, MonthlyReport, Penalty
from apps.reports.reporting_service import (
    get_attendance_report,
    get_booking_stats,
    get_staff_performance,
    get_total_revenue,
)
from apps.reports.services import log_action

__all__ = ["generate_monthly_report"]


@transaction.atomic
def generate_monthly_report(
    *,
    branch,
    month: int,
    year: int,
    created_by,
) -> tuple[MonthlyReport, dict[str, Any]]:
    """
    Generate (or regenerate) the monthly report for *branch*.

    Returns:
        A tuple of ``(report_instance, summary_dict)``.
    """
    date_from = datetime.date(year, month, 1)
    if month == 12:
        date_to = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        date_to = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    # --- Aggregate data using existing reporting service ---
    revenue = get_total_revenue(branch.pk, date_from, date_to)
    booking_stats = get_booking_stats(branch.pk, date_from, date_to)
    staff_perf = get_staff_performance(branch.pk, date_from, date_to)
    attendance = get_attendance_report(branch.pk, date_from, date_to)

    # --- Penalty summary (branch-scoped via staff/admin accounts) ---
    branch_account_ids = _branch_account_ids(branch)
    penalty_agg = Penalty.objects.filter(
        account_id__in=branch_account_ids,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).aggregate(
        total_amount=Coalesce(
            Sum("penalty_amount"),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        total_count=Count("pk"),
    )

    # --- Facility log summary ---
    facility_agg = FacilityLog.objects.filter(
        branch=branch,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).aggregate(
        total_cost=Coalesce(
            Sum("cost"),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        total_count=Count("pk"),
        open_count=Count(
            "pk",
            filter=Q(status__in=[
                FacilityLog.LogStatus.PENDING,
                FacilityLog.LogStatus.APPROVED_CASH,
                FacilityLog.LogStatus.APPROVED_CARD,
                FacilityLog.LogStatus.PAID,
            ]),
        ),
    )

    summary: dict[str, Any] = {
        "revenue": {
            "total": str(revenue["total_revenue"]),
            "booking_count": revenue["booking_count"],
        },
        "bookings": {
            "total": booking_stats["total"],
            "pending": booking_stats["pending"],
            "paid": booking_stats["paid"],
            "canceled": booking_stats["canceled"],
        },
        "attendance": attendance,
        "staff_performance": staff_perf,
        "penalties": {
            "total_amount": str(penalty_agg["total_amount"]),
            "count": penalty_agg["total_count"],
        },
        "facility_issues": {
            "total_cost": str(facility_agg["total_cost"]),
            "count": facility_agg["total_count"],
            "open": facility_agg["open_count"],
        },
    }

    report, _created = MonthlyReport.objects.update_or_create(
        branch=branch,
        month=month,
        year=year,
        defaults={
            "created_by": created_by,
            "summary_notes": json.dumps(summary, default=str),
        },
    )

    director_account = (
        created_by.account if hasattr(created_by, "account") else None
    )
    log_action(
        account=director_account,
        action="monthly_report.generated",
        entity_type="MonthlyReport",
        entity_id=report.pk,
        after_data={
            "id": report.pk,
            "branch_id": report.branch_id,  # type: ignore[attr-defined]
            "month": report.month,
            "year": report.year,
        },
    )

    return report, summary


def _branch_account_ids(branch) -> list[int]:
    """Collect Account IDs of all staff and admins in the branch."""
    staff_ids = list(
        Staff.objects.filter(branch=branch)
        .values_list("account_id", flat=True),
    )
    admin_ids = list(
        Administrator.objects.filter(branch=branch)
        .values_list("account_id", flat=True),
    )
    return staff_ids + admin_ids
