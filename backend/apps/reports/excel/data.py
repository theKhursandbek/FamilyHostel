"""
Build a ``MonthData`` snapshot from the database for one branch + year + month.

This module performs all the queries; ``layout.py`` then renders them.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from apps.accounts.models import Administrator, Staff
from apps.admin_panel.models import SystemSettings
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.reports.models import FacilityLog, Penalty, SalaryAdjustment
from apps.staff.models import Attendance, ShiftAssignment

from .layout import (
    AdminPanelInputs,
    EXPENSE_HEADERS,
    MonthData,
    PANEL_COUNT,
    ShiftRow,
    StaffAttendanceRow,
)

# Map FacilityLog.type → index in EXPENSE_HEADERS
_FACILITY_TYPE_TO_IDX = {
    FacilityLog.FacilityType.PRODUCTS:   0,  # Продукты
    FacilityLog.FacilityType.DETERGENTS: 1,  # Моющие средства
    FacilityLog.FacilityType.TELECOM:    2,  # Телеком-я харажати
    FacilityLog.FacilityType.REPAIR:     3,  # Ремонт
    FacilityLog.FacilityType.UTILITIES:  4,  # Коммуналка
    FacilityLog.FacilityType.OTHER:      5,  # Прочие
}
assert len(EXPENSE_HEADERS) == 6  # safety


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    days = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, days)


def _admin_name_by_account(branch_id: int) -> dict[int, str]:
    return {
        a.account_id: a.full_name
        for a in Administrator.objects.filter(branch_id=branch_id)
    }


def _admin_assignments(branch_id: int, start: dt.date, end: dt.date,
                       names: dict[int, str]) -> dict[tuple[dt.date, str], str]:
    """Map (date, shift_type) → admin full_name based on ShiftAssignment."""
    out: dict[tuple[dt.date, str], str] = {}
    qs = ShiftAssignment.objects.filter(
        branch_id=branch_id,
        role=ShiftAssignment.Role.ADMIN,
        date__range=(start, end),
    )
    for sa in qs:
        out[(sa.date, sa.shift_type)] = names.get(sa.account_id, "")
    return out


def _income_buckets(branch_id: int, start: dt.date, end: dt.date,
                    assignments: dict[tuple[dt.date, str], str]):
    """
    Sum Booking + Payment numbers per (date, shift_type).

    A booking is attributed to its check_in_date. Payment-method breakdown
    comes from Payment rows on bookings with the same date. For each date we
    split the totals between day & night by the proportion of admin
    assignments that exist (default = 100 % to whichever shift has an admin;
    if both, 50/50; if neither, all to day).
    """
    bookings = Booking.objects.filter(
        branch_id=branch_id,
        status=Booking.BookingStatus.PAID,
        check_in_date__range=(start, end),
    ).values("id", "check_in_date", "final_price")

    payments = Payment.objects.filter(
        booking__branch_id=branch_id,
        booking__status=Booking.BookingStatus.PAID,
        booking__check_in_date__range=(start, end),
        is_paid=True,
    ).values("booking__check_in_date", "method", "payment_type", "amount")

    by_date: dict[dt.date, dict[str, Decimal]] = defaultdict(
        lambda: {"total": Decimal(0), "terminal": Decimal(0),
                 "qr": Decimal(0), "card": Decimal(0), "online": Decimal(0)},
    )
    for b in bookings:
        d = b["check_in_date"]
        by_date[d]["total"] += b["final_price"] or Decimal(0)
    for p in payments:
        d = p["booking__check_in_date"]
        amt = p["amount"] or Decimal(0)
        m = p["method"]
        if m == Payment.PaymentMethod.TERMINAL:
            by_date[d]["terminal"] += amt
        elif m == Payment.PaymentMethod.QR:
            by_date[d]["qr"] += amt
        elif m == Payment.PaymentMethod.CARD_TRANSFER:
            by_date[d]["card"] += amt
        if p["payment_type"] == Payment.PaymentType.ONLINE:
            by_date[d]["online"] += amt

    day_inc: dict[dt.date, dict[str, Decimal]] = {}
    night_inc: dict[dt.date, dict[str, Decimal]] = {}
    for d, totals in by_date.items():
        has_day = bool(assignments.get((d, "day")))
        has_night = bool(assignments.get((d, "night")))
        if has_day and has_night:
            split = (Decimal("0.5"), Decimal("0.5"))
        elif has_night and not has_day:
            split = (Decimal(0), Decimal(1))
        else:
            split = (Decimal(1), Decimal(0))
        day_inc[d] = {k: (v * split[0]) for k, v in totals.items()}
        night_inc[d] = {k: (v * split[1]) for k, v in totals.items()}
    return day_inc, night_inc


def _expense_buckets(branch_id: int, start: dt.date, end: dt.date):
    """(date, shift_type) → list[6] of expense decimals."""
    qs = (
        FacilityLog.objects
        .filter(branch_id=branch_id, created_at__date__range=(start, end))
        .values("created_at__date", "shift_type", "type")
        .annotate(total=Sum("cost"))
    )
    out: dict[tuple[dt.date, str], list[Decimal]] = defaultdict(
        lambda: [Decimal(0)] * 6,
    )
    for r in qs:
        d = r["created_at__date"]
        shift = r["shift_type"] or "day"
        idx = _FACILITY_TYPE_TO_IDX.get(r["type"])
        if idx is None:
            continue
        out[(d, shift)][idx] += r["total"] or Decimal(0)
    return out


def _adjustments_for(branch_id: int, year: int, month: int):
    """Aggregate :class:`SalaryAdjustment` rows for the month."""
    qs = (
        SalaryAdjustment.objects
        .filter(branch_id=branch_id, year=year, month=month)
        .values("account_id", "kind")
        .annotate(total=Sum("amount"))
    )
    out: dict[int, dict[str, Decimal]] = defaultdict(
        lambda: {"fine": Decimal(0), "bonus_plus": Decimal(0)}
    )
    for r in qs:
        if r["kind"] == SalaryAdjustment.Kind.PENALTY:
            out[r["account_id"]]["fine"] = r["total"] or Decimal(0)
        elif r["kind"] == SalaryAdjustment.Kind.BONUS_PLUS:
            out[r["account_id"]]["bonus_plus"] = r["total"] or Decimal(0)
    return out


def _advances_for(account_ids, year: int, month: int):
    """Sum of paid advances (``SalaryRecord.kind='advance'``) for the month."""
    from apps.payments.models import SalaryRecord
    start, end = _month_bounds(year, month)
    qs = (
        SalaryRecord.objects
        .filter(
            account_id__in=list(account_ids),
            kind=SalaryRecord.SalaryKind.ADVANCE,
            period_start__gte=start,
            period_end__lte=end,
        )
        .values("account_id")
        .annotate(total=Sum("amount"))
    )
    return {r["account_id"]: r["total"] or Decimal(0) for r in qs}


def _staff_rows(branch_id: int, year: int, month: int) -> list[StaffAttendanceRow]:
    days = calendar.monthrange(year, month)[1]
    start, end = _month_bounds(year, month)

    staff_qs = (
        Staff.objects
        .filter(branch_id=branch_id, is_active=True)
        .order_by("full_name")
    )

    att_qs = Attendance.objects.filter(
        branch_id=branch_id,
        date__range=(start, end),
        account__staff_profile__branch_id=branch_id,
    ).values("account_id", "date", "status")
    present_map: dict[int, set[dt.date]] = defaultdict(set)
    for a in att_qs:
        if a["status"] in (
            Attendance.AttendanceStatus.PRESENT,
            Attendance.AttendanceStatus.LATE,
        ):
            present_map[a["account_id"]].add(a["date"])

    pen_qs = (
        Penalty.objects
        .filter(created_at__date__range=(start, end),
                account__staff_profile__branch_id=branch_id)
        .values("account_id")
        .annotate(total=Sum("penalty_amount"))
    )
    fine_map = {r["account_id"]: r["total"] or Decimal(0) for r in pen_qs}

    staff_account_ids = list(staff_qs.values_list("account_id", flat=True))
    adj_map = _adjustments_for(branch_id, year, month)
    adv_map = _advances_for(staff_account_ids, year, month)

    rows: list[StaffAttendanceRow] = []
    for s in staff_qs:
        present_dates = present_map.get(s.account_id, set())
        flags = [
            dt.date(year, month, d) in present_dates
            for d in range(1, days + 1)
        ]
        fine = (
            fine_map.get(s.account_id, Decimal(0))
            + adj_map.get(s.account_id, {}).get("fine", Decimal(0))
        )
        rows.append(StaffAttendanceRow(
            full_name=s.full_name,
            present_flags=flags,
            fine=fine,
            advance=adv_map.get(s.account_id, Decimal(0)),
        ))
    return rows


def _admin_panels(branch_id: int, year: int, month: int) -> list[AdminPanelInputs]:
    adjustments = _adjustments_for(branch_id, year, month)

    panels: list[AdminPanelInputs] = []
    admin_qs = list(
        Administrator.objects
        .filter(branch_id=branch_id, is_active=True)
        .order_by("full_name")[:PANEL_COUNT]
    )
    advances = _advances_for([a.account_id for a in admin_qs], year, month)
    for a in admin_qs:
        adj = adjustments.get(a.account_id, {})
        panels.append(AdminPanelInputs(
            full_name=a.full_name,
            fine=adj.get("fine", Decimal(0)),
            advance=advances.get(a.account_id, Decimal(0)),
            bonus_plus=adj.get("bonus_plus", Decimal(0)),
            bonus_pct=0.05,
        ))
    return panels


def build_month_data(*, branch, year: int, month: int,
                     viewer_name: str) -> MonthData:
    settings = SystemSettings.objects.first() or SystemSettings()
    daily_rate = int(settings.staff_shift_rate)
    admin_shift_rate = int(settings.admin_shift_rate or 100_000)

    start, end = _month_bounds(year, month)

    names = _admin_name_by_account(branch.id)
    ass = _admin_assignments(branch.id, start, end, names)
    day_inc, night_inc = _income_buckets(branch.id, start, end, ass)
    exp_buckets = _expense_buckets(branch.id, start, end)

    days = calendar.monthrange(year, month)[1]
    day_rows: list[ShiftRow] = []
    night_rows: list[ShiftRow] = []
    for i in range(days):
        d = dt.date(year, month, i + 1)
        di = day_inc.get(d, {})
        ni = night_inc.get(d, {})
        day_rows.append(ShiftRow(
            admin_name=ass.get((d, "day"), ""),
            income_total=di.get("total", Decimal(0)),
            income_terminal=di.get("terminal", Decimal(0)),
            income_qr=di.get("qr", Decimal(0)),
            income_card=di.get("card", Decimal(0)),
            income_online=di.get("online", Decimal(0)),
            expenses=exp_buckets.get((d, "day"), [Decimal(0)] * 6),
        ))
        night_rows.append(ShiftRow(
            admin_name=ass.get((d, "night"), ""),
            income_total=ni.get("total", Decimal(0)),
            income_terminal=ni.get("terminal", Decimal(0)),
            income_qr=ni.get("qr", Decimal(0)),
            income_card=ni.get("card", Decimal(0)),
            income_online=ni.get("online", Decimal(0)),
            expenses=exp_buckets.get((d, "night"), [Decimal(0)] * 6),
        ))
    panels = _admin_panels(branch.id, year, month)
    staff = _staff_rows(branch.id, year, month)

    return MonthData(
        year=year, month=month,
        branch_name=branch.name,
        viewer=viewer_name,
        daily_rate=daily_rate,
        admin_shift_rate=admin_shift_rate,
        day_rows=day_rows,
        night_rows=night_rows,
        admin_panels=panels,
        staff=staff,
    )
