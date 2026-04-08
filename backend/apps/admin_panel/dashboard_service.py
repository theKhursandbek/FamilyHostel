"""
Dashboard service — aggregated data for Admin, Director, and Super Admin
dashboards (Step 21.3).

Each function returns a plain ``dict`` ready for JSON serialization.
All queries use Django ORM aggregation to avoid N+1 problems.

Functions:
    - get_admin_dashboard(account)    → admin's shift/bookings/revenue/cash today
    - get_director_dashboard(branch)  → branch-level KPIs
    - get_super_admin_dashboard()     → system-wide overview
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Account, Administrator, Staff
from apps.admin_panel.models import CashSession
from apps.bookings.models import Booking
from apps.branches.models import Branch, Room
from apps.cleaning.models import CleaningTask
from apps.payments.models import Payment
from apps.staff.models import Attendance, ShiftAssignment


def _today() -> date:
    return timezone.localdate()


def _month_start() -> date:
    today = _today()
    return today.replace(day=1)


# ==============================================================================
# ADMIN DASHBOARD
# ==============================================================================


def get_admin_dashboard(account: Account) -> dict:
    """
    Dashboard data for an Administrator.

    Includes:
        - current_shift   — today's shift assignment info
        - bookings_today  — bookings handled today (count + breakdown)
        - revenue_today   — paid revenue today
        - active_rooms    — room status summary for the admin's branch
        - cash_session    — today's cash session summary
    """
    admin_profile = account.administrator_profile  # type: ignore[attr-defined]
    branch = admin_profile.branch
    today = _today()

    # --- Current shift ---
    shift = (
        ShiftAssignment.objects.filter(
            account=account,
            branch=branch,
            date=today,
        )
        .values("shift_type", "date", "role")
        .first()
    )

    # --- Bookings today ---
    bookings_qs = Booking.objects.filter(
        branch=branch,
        created_at__date=today,
    )
    bookings_agg = bookings_qs.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        paid=Count("id", filter=Q(status="paid")),
        canceled=Count("id", filter=Q(status="canceled")),
    )

    # --- Revenue today (only paid payments) ---
    revenue = (
        Payment.objects.filter(
            booking__branch=branch,
            is_paid=True,
            paid_at__date=today,
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    # --- Active rooms ---
    rooms_agg = (
        Room.objects.filter(branch=branch, is_active=True)
        .aggregate(
            total=Count("id"),
            available=Count("id", filter=Q(status="available")),
            booked=Count("id", filter=Q(status="booked")),
            occupied=Count("id", filter=Q(status="occupied")),
            cleaning=Count("id", filter=Q(status="cleaning")),
        )
    )

    # --- Cash session ---
    cash = (
        CashSession.objects.filter(
            admin=admin_profile,
            branch=branch,
            start_time__date=today,
        )
        .values(
            "id", "shift_type", "start_time", "end_time",
            "opening_balance", "closing_balance", "difference",
        )
        .first()
    )

    return {
        "branch": {"id": branch.pk, "name": branch.name},
        "current_shift": shift,
        "bookings_today": bookings_agg,
        "revenue_today": str(revenue),
        "active_rooms": rooms_agg,
        "cash_session": cash,
    }


# ==============================================================================
# DIRECTOR DASHBOARD
# ==============================================================================


def get_director_dashboard(branch: Branch) -> dict:
    """
    Dashboard data for a Director (branch-level).

    Includes:
        - revenue          — today & this month
        - booking_stats    — today & this month counts by status
        - staff_performance — cleaning tasks completed per staff today
        - attendance        — today's summary
        - pending_issues    — cleaning retries + open penalties
    """
    today = _today()
    month_start = _month_start()

    # --- Revenue ---
    revenue_today = (
        Payment.objects.filter(
            booking__branch=branch,
            is_paid=True,
            paid_at__date=today,
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    revenue_month = (
        Payment.objects.filter(
            booking__branch=branch,
            is_paid=True,
            paid_at__date__gte=month_start,
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    # --- Booking stats ---
    def _booking_stats(date_filter: Q) -> dict:
        return Booking.objects.filter(
            branch=branch,
        ).filter(date_filter).aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            paid=Count("id", filter=Q(status="paid")),
            canceled=Count("id", filter=Q(status="canceled")),
        )

    bookings_today = _booking_stats(Q(created_at__date=today))
    bookings_month = _booking_stats(Q(created_at__date__gte=month_start))

    # --- Staff performance (cleaning tasks completed today) ---
    staff_performance = list(
        CleaningTask.objects.filter(
            branch=branch,
            status="completed",
            completed_at__date=today,
            assigned_to__isnull=False,
        )
        .values("assigned_to__full_name")
        .annotate(tasks_completed=Count("id"))
        .order_by("-tasks_completed")
    )

    # --- Attendance summary (today) ---
    attendance_agg = (
        Attendance.objects.filter(branch=branch, date=today)
        .aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status="present")),
            late=Count("id", filter=Q(status="late")),
            absent=Count("id", filter=Q(status="absent")),
        )
    )

    # --- Pending issues ---
    cleaning_retries = CleaningTask.objects.filter(
        branch=branch,
        status="retry_required",
    ).count()

    pending_cleaning = CleaningTask.objects.filter(
        branch=branch,
        status="pending",
    ).count()

    return {
        "branch": {"id": branch.pk, "name": branch.name},
        "revenue": {
            "today": str(revenue_today),
            "month": str(revenue_month),
        },
        "booking_stats": {
            "today": bookings_today,
            "month": bookings_month,
        },
        "staff_performance": staff_performance,
        "attendance_summary": attendance_agg,
        "pending_issues": {
            "cleaning_retries": cleaning_retries,
            "pending_cleaning": pending_cleaning,
        },
    }


# ==============================================================================
# SUPER ADMIN DASHBOARD
# ==============================================================================


def get_super_admin_dashboard() -> dict:
    """
    System-wide dashboard for Super Admin.

    Includes:
        - total_branches     — active / total
        - total_revenue      — all branches today & month
        - top_branch         — highest revenue this month
        - staff_admin_count  — staff & admin headcounts
        - system_activity    — bookings, cleaning tasks, recent blocks
    """
    today = _today()
    month_start = _month_start()

    # --- Branches ---
    branches_agg = Branch.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )

    # --- Revenue ---
    revenue_today = (
        Payment.objects.filter(is_paid=True, paid_at__date=today)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    revenue_month = (
        Payment.objects.filter(is_paid=True, paid_at__date__gte=month_start)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    # --- Top branch (by revenue this month) ---
    top_branch_data = (
        Payment.objects.filter(is_paid=True, paid_at__date__gte=month_start)
        .values("booking__branch__id", "booking__branch__name")
        .annotate(total_revenue=Sum("amount"))
        .order_by("-total_revenue")
        .first()
    )
    if top_branch_data:
        top_branch = {
            "id": top_branch_data["booking__branch__id"],
            "name": top_branch_data["booking__branch__name"],
            "revenue": str(top_branch_data["total_revenue"]),
        }
    else:
        top_branch = None

    # --- Staff & admin counts ---
    staff_count = Staff.objects.filter(is_active=True).count()
    admin_count = Administrator.objects.filter(is_active=True).count()

    # --- System activity ---
    bookings_today = Booking.objects.filter(created_at__date=today).count()
    bookings_month = Booking.objects.filter(
        created_at__date__gte=month_start,
    ).count()

    cleaning_today = CleaningTask.objects.filter(
        created_at__date=today,
    ).aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
        pending=Count("id", filter=Q(status="pending")),
        retry=Count("id", filter=Q(status="retry_required")),
    )

    # Recent suspicious activity blocks (Step 21.2 integration)
    from apps.accounts.models import SuspiciousActivity

    active_blocks = SuspiciousActivity.objects.filter(
        is_blocked=True,
        blocked_until__gt=timezone.now(),
    ).count()

    return {
        "branches": branches_agg,
        "revenue": {
            "today": str(revenue_today),
            "month": str(revenue_month),
        },
        "top_branch": top_branch,
        "personnel": {
            "active_staff": staff_count,
            "active_admins": admin_count,
        },
        "system_activity": {
            "bookings_today": bookings_today,
            "bookings_month": bookings_month,
            "cleaning_today": cleaning_today,
            "active_security_blocks": active_blocks,
        },
    }
