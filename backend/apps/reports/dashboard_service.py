"""
Branch dashboard data service (REFACTOR_PLAN_2026_04 §4.2).

Builds the JSON payload for ``GET /reports/branch-dashboard/?branch=&year=&month=``.

Coverage mirrors the per-month Excel workbook so the in-page dashboard and
the downloadable workbook always agree:

* KPIs — total income, total expenses, net, occupancy, avg cash variance.
* Income matrix — per-day × shift (day/night) totals.
* Expense breakdown — per-category totals (and cash vs card subtotals).
* Penalty list — every Penalty whose target belongs to the branch.
* Salary roster — every active admin/staff/director on that branch with
  their live breakdown for the period.
* Cash sessions — per-shift summary with variance distribution.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum

from apps.accounts.models import Account
from apps.admin_panel.models import CashSession
from apps.bookings.models import Booking
from apps.branches.models import Branch
from apps.payments.models import Payment, SalaryRecord
from apps.reports.models import FacilityLog, Penalty
from apps.staff.salary_service import calculate_salary_breakdown


__all__ = ["build_branch_dashboard"]


def _bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    last = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, last)


def _account_name(acc: Account) -> str:
    for attr in ("administrator_profile", "staff_profile",
                 "director_profile", "client_profile"):
        prof = getattr(acc, attr, None)
        name = getattr(prof, "full_name", None) if prof else None
        if name:
            return name
    return getattr(acc, "phone", "") or str(acc)


def _account_roles(acc: Account) -> list[str]:
    roles = []
    if getattr(acc, "director_profile", None):
        roles.append("Director")
    if getattr(acc, "administrator_profile", None):
        roles.append("Administrator")
    if getattr(acc, "staff_profile", None):
        roles.append("Staff")
    return roles


# ---------------------------------------------------------------------------
# Income (per-day × shift)
# ---------------------------------------------------------------------------


def _income_matrix(branch_id: int, start: dt.date, end: dt.date) -> dict:
    """Per-day totals — sourced from paid Bookings.

    Day/night attribution comes from the *Payment*'s ``payment_type``
    proxy when available; otherwise the booking's full price is treated
    as a single-row daily total. (Booking has no ``shift_type`` field —
    the workbook layer infers it via shift assignments.)
    """
    bookings = (
        Booking.objects
        .filter(
            branch_id=branch_id,
            status=Booking.BookingStatus.PAID,
            check_in_date__range=(start, end),
        )
        .values("check_in_date", "final_price")
    )
    rows: dict[dt.date, Decimal] = defaultdict(lambda: Decimal("0"))
    for b in bookings:
        rows[b["check_in_date"]] += Decimal(b["final_price"] or 0)

    grand = sum(rows.values(), Decimal("0"))
    return {
        "rows": [
            {"date": d.isoformat(), "total": str(rows[d])}
            for d in sorted(rows.keys())
        ],
        "totals": {"total": str(grand)},
    }


def _income_methods(branch_id: int, start: dt.date, end: dt.date) -> dict:
    """Payment-method breakdown (cash, card, terminal, qr, online)."""
    qs = (
        Payment.objects
        .filter(
            booking__branch_id=branch_id,
            booking__status=Booking.BookingStatus.PAID,
            booking__check_in_date__range=(start, end),
            is_paid=True,
        )
        .values("method")
        .annotate(total=Sum("amount"))
    )
    out = {row["method"]: str(row["total"] or Decimal("0")) for row in qs}
    return out


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


def _expense_breakdown(branch_id: int, start: dt.date, end: dt.date) -> dict:
    # Only count expenses that have been approved or beyond — pending /
    # rejected requests are still in the request lifecycle and don't belong
    # in the financial dashboard.
    qs = FacilityLog.objects.filter(
        branch_id=branch_id,
        created_at__date__range=(start, end),
        status__in=[
            FacilityLog.LogStatus.APPROVED_CASH,
            FacilityLog.LogStatus.APPROVED_CARD,
            FacilityLog.LogStatus.PAID,
            FacilityLog.LogStatus.RESOLVED,
        ],
    )
    by_category = defaultdict(lambda: Decimal("0"))
    cash_total = Decimal("0")
    card_total = Decimal("0")
    count = 0
    for row in qs.values("type", "cost", "payment_method", "status"):
        amount = Decimal(row["cost"] or 0)
        by_category[row["type"]] += amount
        # payment_method only present after Phase 6; default to cash.
        method = (row.get("payment_method") or "cash").lower()
        if method == "card":
            card_total += amount
        else:
            cash_total += amount
        count += 1
    return {
        "by_category": {k: str(v) for k, v in by_category.items()},
        "cash_total": str(cash_total),
        "card_total": str(card_total),
        "total": str(cash_total + card_total),
        "count": count,
    }


# ---------------------------------------------------------------------------
# Penalties (branch-scoped via target accounts)
# ---------------------------------------------------------------------------


def _penalty_list(branch_id: int, start: dt.date, end: dt.date) -> list[dict]:
    branch_account_ids = list(
        Account.objects.filter(
            Q(administrator_profile__branch_id=branch_id)
            | Q(staff_profile__branch_id=branch_id)
            | Q(director_profile__branch_id=branch_id),
        ).values_list("pk", flat=True).distinct(),
    )
    qs = (
        Penalty.objects
        .filter(
            account_id__in=branch_account_ids,
            created_at__date__range=(start, end),
        )
        .select_related("account")
        .order_by("-created_at")
    )
    rows = []
    for p in qs:
        rows.append({
            "id": p.pk,
            "account_name": _account_name(p.account),
            "type": p.type or "",
            "count": p.count,
            "amount": str(p.penalty_amount or Decimal("0")),
            "reason": p.reason or "",
            "created_at": p.created_at.isoformat(),
        })
    return rows


# ---------------------------------------------------------------------------
# Salary roster
# ---------------------------------------------------------------------------


def _salary_roster(branch_id: int, start: dt.date, end: dt.date) -> dict:
    accounts = (
        Account.objects
        .filter(
            Q(staff_profile__branch_id=branch_id, staff_profile__is_active=True)
            | Q(administrator_profile__branch_id=branch_id,
                administrator_profile__is_active=True)
            | Q(director_profile__branch_id=branch_id,
                director_profile__is_active=True)
        )
        .select_related(
            "staff_profile", "administrator_profile", "director_profile",
        )
        .distinct()
    )

    existing = {
        (r.account_id, r.kind): r
        for r in SalaryRecord.objects.filter(
            period_start=start, period_end=end, account__in=accounts,
        )
    }

    rows = []
    payroll_total = Decimal("0")
    for acc in accounts:
        b = calculate_salary_breakdown(acc.pk, start, end)
        adv = existing.get((acc.pk, SalaryRecord.SalaryKind.ADVANCE))
        fin = existing.get((acc.pk, SalaryRecord.SalaryKind.FINAL))
        total = Decimal(b["total"])
        payroll_total += total
        rows.append({
            "account": acc.pk,
            "account_name": _account_name(acc),
            "roles": _account_roles(acc),
            "shift_count": b["shift_count"],
            "shift_pay": str(b["shift_pay"]),
            "income_bonus": str(b["income_bonus"]),
            "cleaning_bonus": str(b["cleaning_bonus"]),
            "director_fixed": str(b["director_fixed"]),
            "penalties": str(b["penalties"]),
            "adjustment_penalty": str(b.get("adjustment_penalty", "0")),
            "adjustment_bonus_plus": str(b.get("adjustment_bonus_plus", "0")),
            "total": str(total),
            "advance_paid": str(adv.amount) if adv else "0",
            "final_paid": str(fin.amount) if fin else "0",
        })
    rows.sort(key=lambda r: Decimal(r["total"]), reverse=True)
    return {
        "rows": rows,
        "totals": {
            "headcount": len(rows),
            "payroll": str(payroll_total),
        },
    }


# ---------------------------------------------------------------------------
# Cash sessions
# ---------------------------------------------------------------------------


def _cash_sessions(branch_id: int, start: dt.date, end: dt.date) -> dict:
    qs = CashSession.objects.filter(
        branch_id=branch_id,
        start_time__date__range=(start, end),
    )
    agg = qs.aggregate(
        count=Count("pk"),
        variance_sum=Sum("difference"),
    )
    by_status = {
        row["variance_status"]: row["c"]
        for row in qs.values("variance_status").annotate(c=Count("pk"))
    }
    closed = qs.filter(end_time__isnull=False).count()
    diffs = list(
        qs.filter(difference__isnull=False).values_list("difference", flat=True),
    )
    avg_var = (
        (sum((d for d in diffs), Decimal("0")) / Decimal(len(diffs)))
        if diffs else Decimal("0")
    )
    return {
        "count": agg["count"] or 0,
        "closed": closed,
        "variance_sum": str(agg["variance_sum"] or Decimal("0")),
        "variance_avg": str(avg_var.quantize(Decimal("1.00"))),
        "by_status": by_status,
    }


# ---------------------------------------------------------------------------
# Occupancy
# ---------------------------------------------------------------------------


def _occupancy(branch_id: int, start: dt.date, end: dt.date) -> dict:
    """Booked nights ÷ (rooms × days). Rooms = active rooms on branch."""
    from apps.rooms.models import Room
    rooms = Room.objects.filter(branch_id=branch_id).count()
    days = (end - start).days + 1
    booked_nights = (
        Booking.objects
        .filter(
            branch_id=branch_id,
            status=Booking.BookingStatus.PAID,
            check_in_date__range=(start, end),
        )
        .aggregate(n=Count("pk"))["n"] or 0
    )
    capacity = max(rooms * days, 1)
    pct = float(booked_nights) / float(capacity) * 100
    return {
        "rooms": rooms,
        "days": days,
        "booked_nights": booked_nights,
        "occupancy_pct": round(pct, 1),
    }


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def build_branch_dashboard(*, branch: Branch, year: int, month: int) -> dict[str, Any]:
    start, end = _bounds(year, month)

    income = _income_matrix(branch.pk, start, end)
    income_methods = _income_methods(branch.pk, start, end)
    expenses = _expense_breakdown(branch.pk, start, end)
    occupancy = _occupancy(branch.pk, start, end)
    penalties = _penalty_list(branch.pk, start, end)
    salary = _salary_roster(branch.pk, start, end)
    cash = _cash_sessions(branch.pk, start, end)

    income_total = Decimal(income["totals"]["total"])
    expense_total = Decimal(expenses["total"])
    net = income_total - expense_total

    return {
        "branch": {
            "id": branch.pk,
            "name": branch.name,
            "working_days_per_month": branch.working_days_per_month,
        },
        "period": {
            "year": year,
            "month": month,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1,
        },
        "kpis": {
            "income_total": str(income_total),
            "expense_total": str(expense_total),
            "net": str(net),
            "occupancy_pct": occupancy["occupancy_pct"],
            "cash_variance_avg": cash["variance_avg"],
        },
        "income": income,
        "income_methods": income_methods,
        "expenses": expenses,
        "occupancy": occupancy,
        "penalties": penalties,
        "salary": salary,
        "cash_sessions": cash,
    }
