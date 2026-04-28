"""
Salary lifecycle service (REFACTOR_PLAN_2026_04 §3.3 – §3.6).

Calendar-driven payroll with two windows:

* **Day 15 – 20 of month M** — CEO pays *advance* for month M.
  ``advance = (monthly_salary / branch.working_days_per_month) ×
  worked_days_1st_to_15th``
* **Day 1 – 5 of month M+1** — CEO pays the *final* (remainder) for month M.
  ``final = full_month_salary − sum(advance SalaryRecords for M)``

If the day 1–5 window also lapses, ``pay_late`` is the manual recovery
endpoint — CEO-only, requires a written reason, audit-logged (Q11).
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from apps.accounts.models import Account, Administrator, Director, Staff
from apps.payments.models import SalaryAuditLog, SalaryRecord
from apps.reports.services import log_action
from apps.staff.salary_service import (
    calculate_salary_breakdown,
    count_valid_shifts,
    get_system_settings,
    resolve_director_payout,
    resolve_per_shift_rate,
)


__all__ = [
    "advance_window",
    "final_window",
    "is_in_window",
    "compute_advance_amount",
    "pay_advance",
    "pay_final",
    "pay_late",
    "WindowError",
]


class WindowError(Exception):
    """Raised when a payroll action is requested outside its calendar window."""


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


def _month_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, 1), datetime.date(year, month, last)


def advance_window(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """Day 15–20 of the same month."""
    return datetime.date(year, month, 15), datetime.date(year, month, 20)


def final_window(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """Day 1–5 of the *next* month (the period being paid is `M`)."""
    if month == 12:
        return datetime.date(year + 1, 1, 1), datetime.date(year + 1, 1, 5)
    return datetime.date(year, month + 1, 1), datetime.date(year, month + 1, 5)


def is_in_window(today: datetime.date, start: datetime.date, end: datetime.date) -> bool:
    return start <= today <= end


# ---------------------------------------------------------------------------
# Targets — every active payroll-eligible account on every branch
# ---------------------------------------------------------------------------


def _payroll_accounts():
    """Active Admins, Staff and Directors across the org (CEO scope)."""
    return (
        Account.objects
        .filter(
            Q(administrator_profile__is_active=True)
            | Q(staff_profile__is_active=True)
            | Q(director_profile__is_active=True)
        )
        .select_related(
            "administrator_profile", "staff_profile", "director_profile",
        )
        .distinct()
    )


def _branch_for_account(account) -> tuple[int | None, int]:
    """Return ``(branch_id, working_days_per_month)`` for the account."""
    from apps.branches.models import Branch
    for attr in ("administrator_profile", "staff_profile", "director_profile"):
        prof = getattr(account, attr, None)
        if prof and prof.branch_id:
            wd = (
                Branch.objects
                .filter(pk=prof.branch_id)
                .values_list("working_days_per_month", flat=True)
                .first()
            )
            return prof.branch_id, int(wd or 26)
    return None, 26


# ---------------------------------------------------------------------------
# Advance computation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdvancePreview:
    account_id: int
    monthly_salary: Decimal       # full month salary if it ran today (no bonuses)
    worked_days: int              # valid shifts in days 1–15
    working_days_per_month: int
    amount: Decimal               # final advance value


def _monthly_base_for_advance(account, period_start, period_end) -> Decimal:
    """Per §3.4: monthly_salary is the full-month figure WITHOUT bonuses
    that depend on whole-month income.

    For staff/admin: ``shift_rate × shift_count`` for the WHOLE month.
    For directors: their fixed salary (no GM bonus, no income bonus).
    """
    settings = get_system_settings()

    director = Director.objects.filter(account_id=account.pk).first()
    if director is not None:
        fixed, _gm = resolve_director_payout(director, settings)
        return fixed

    rate = resolve_per_shift_rate(account.pk, settings)
    full_shifts = count_valid_shifts(account.pk, period_start, period_end)
    return Decimal(full_shifts) * rate


def compute_advance_amount(account, year: int, month: int) -> AdvancePreview:
    """Return the advance computation per §3.4 for one account."""
    period_start, period_end = _month_bounds(year, month)
    half = datetime.date(year, month, 15)

    monthly_salary = _monthly_base_for_advance(account, period_start, period_end)
    worked = count_valid_shifts(account.pk, period_start, half)
    _, wdpm = _branch_for_account(account)

    if monthly_salary <= 0 or wdpm <= 0:
        return AdvancePreview(account.pk, Decimal("0"), worked, wdpm, Decimal("0"))

    # Directors: pay half the fixed salary as advance (proportional to
    # the standard 26-day month would double-count bonuses they don't get).
    if Director.objects.filter(account_id=account.pk).exists():
        amount = (monthly_salary / Decimal("2")).quantize(Decimal("1."))
        return AdvancePreview(account.pk, monthly_salary, worked, wdpm, amount)

    daily = monthly_salary / Decimal(wdpm)
    amount = (daily * Decimal(worked)).quantize(Decimal("1."))
    return AdvancePreview(account.pk, monthly_salary, worked, wdpm, amount)


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


@transaction.atomic
def pay_advance(*, actor, year: int, month: int,
                force: bool = False) -> list[SalaryRecord]:
    """Bulk-create ``SalaryRecord(kind=advance)`` for every active employee.

    Window: day 15–20 of *M*. Pass ``force=True`` to bypass the check
    (used only by admin overrides — never from the standard UI).
    """
    today = datetime.date.today()
    start, end = advance_window(year, month)
    if not force and not is_in_window(today, start, end):
        raise WindowError(
            f"Advance window for {year}-{month:02d} is {start} → {end}; today is {today}."
        )

    period_start, period_end = _month_bounds(year, month)
    created: list[SalaryRecord] = []

    for account in _payroll_accounts():
        # Skip if an advance row already exists for this period.
        if SalaryRecord.objects.filter(
            account=account,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.ADVANCE,
        ).exists():
            continue

        preview = compute_advance_amount(account, year, month)
        if preview.amount <= 0:
            continue

        record = SalaryRecord.objects.create(
            account=account,
            amount=preview.amount,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.ADVANCE,
            status=SalaryRecord.SalaryStatus.PAID,
        )
        SalaryAuditLog.objects.create(
            record=record,
            actor=actor,
            action=SalaryAuditLog.Action.MARKED_PAID,
            before_amount=None,
            after_amount=record.amount,
            note=f"Advance for {year}-{month:02d}",
        )
        log_action(
            account=actor,
            action="salary.advance_paid",
            entity_type="SalaryRecord",
            entity_id=record.pk,
            after_data={
                "target_account": account.pk,
                "year": year, "month": month,
                "amount": str(record.amount),
                "worked_days": preview.worked_days,
                "working_days_per_month": preview.working_days_per_month,
            },
        )
        created.append(record)
    return created


def _final_amount(account, year: int, month: int) -> Decimal:
    """Full-month salary minus already-paid advances. Q6: if no advances,
    that equals the full salary by definition."""
    period_start, period_end = _month_bounds(year, month)
    breakdown = calculate_salary_breakdown(account.pk, period_start, period_end)
    full = Decimal(breakdown["total"])
    advances = (
        SalaryRecord.objects
        .filter(
            account=account,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.ADVANCE,
        )
        .aggregate(total=Sum("amount"))
    )["total"] or Decimal("0")
    return max(full - advances, Decimal("0"))


@transaction.atomic
def pay_final(*, actor, year: int, month: int,
              force: bool = False) -> list[SalaryRecord]:
    """Bulk-create ``SalaryRecord(kind=final)`` for every active employee.

    Window: day 1–5 of *M+1*.
    """
    today = datetime.date.today()
    start, end = final_window(year, month)
    if not force and not is_in_window(today, start, end):
        raise WindowError(
            f"Final window for {year}-{month:02d} is {start} → {end}; today is {today}."
        )

    period_start, period_end = _month_bounds(year, month)
    created: list[SalaryRecord] = []

    for account in _payroll_accounts():
        if SalaryRecord.objects.filter(
            account=account,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.FINAL,
        ).exists():
            continue

        amount = _final_amount(account, year, month)
        if amount <= 0:
            continue

        record = SalaryRecord.objects.create(
            account=account,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.FINAL,
            status=SalaryRecord.SalaryStatus.PAID,
        )
        SalaryAuditLog.objects.create(
            record=record,
            actor=actor,
            action=SalaryAuditLog.Action.MARKED_PAID,
            before_amount=None,
            after_amount=record.amount,
            note=f"Final for {year}-{month:02d}",
        )
        log_action(
            account=actor,
            action="salary.final_paid",
            entity_type="SalaryRecord",
            entity_id=record.pk,
            after_data={
                "target_account": account.pk,
                "year": year, "month": month,
                "amount": str(record.amount),
            },
        )
        created.append(record)
    return created


@transaction.atomic
def pay_late(*, actor, year: int, month: int, reason: str) -> list[SalaryRecord]:
    """Q11 — manual late-payment recovery. CEO-only, written reason required.

    Behaviour identical to :func:`pay_final` but bypasses the calendar
    window. Audit log notes the recovery context.
    """
    if not reason or not reason.strip():
        raise ValueError("A written reason is required for late salary recovery.")

    today = datetime.date.today()
    final_end = final_window(year, month)[1]
    if today <= final_end:
        raise WindowError(
            f"Final window for {year}-{month:02d} has not yet closed (closes {final_end})."
        )

    period_start, period_end = _month_bounds(year, month)
    created: list[SalaryRecord] = []

    for account in _payroll_accounts():
        if SalaryRecord.objects.filter(
            account=account,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.FINAL,
        ).exists():
            continue

        amount = _final_amount(account, year, month)
        if amount <= 0:
            continue

        record = SalaryRecord.objects.create(
            account=account,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            kind=SalaryRecord.SalaryKind.FINAL,
            status=SalaryRecord.SalaryStatus.PAID,
        )
        SalaryAuditLog.objects.create(
            record=record,
            actor=actor,
            action=SalaryAuditLog.Action.MARKED_PAID,
            before_amount=None,
            after_amount=record.amount,
            note=f"Late recovery for {year}-{month:02d}: {reason.strip()[:200]}",
        )
        log_action(
            account=actor,
            action="salary.paid_late",
            entity_type="SalaryRecord",
            entity_id=record.pk,
            after_data={
                "target_account": account.pk,
                "year": year, "month": month,
                "amount": str(record.amount),
                "reason": reason.strip(),
            },
        )
        created.append(record)
    return created


# ---------------------------------------------------------------------------
# Status helpers (used by /payments/salary/status/)
# ---------------------------------------------------------------------------


def lifecycle_status(today: datetime.date | None = None) -> dict:
    """Return UI hints for the Salary page calendar buttons.

    Includes the current advance/final windows, the previous month's pay
    state, and the Q11 unpaid-banner trigger.
    """
    today = today or datetime.date.today()

    cur_year, cur_month = today.year, today.month
    if cur_month == 1:
        prev_year, prev_month = cur_year - 1, 12
    else:
        prev_year, prev_month = cur_year, cur_month - 1

    cur_adv_start, cur_adv_end = advance_window(cur_year, cur_month)
    prev_final_start, prev_final_end = final_window(prev_year, prev_month)

    # Has a final row been paid for the previous month?
    prev_period_start, prev_period_end = _month_bounds(prev_year, prev_month)
    prev_paid = SalaryRecord.objects.filter(
        period_start=prev_period_start,
        period_end=prev_period_end,
        kind=SalaryRecord.SalaryKind.FINAL,
    ).exists()
    prev_overdue = (today > prev_final_end) and not prev_paid

    # Has any advance been paid for the current month? Used for label flip.
    cur_period_start, cur_period_end = _month_bounds(cur_year, cur_month)
    cur_advance_paid = SalaryRecord.objects.filter(
        period_start=cur_period_start,
        period_end=cur_period_end,
        kind=SalaryRecord.SalaryKind.ADVANCE,
    ).exists()

    return {
        "today": today.isoformat(),
        "current_month": {"year": cur_year, "month": cur_month},
        "previous_month": {"year": prev_year, "month": prev_month},
        "advance_window": {
            "start": cur_adv_start.isoformat(),
            "end": cur_adv_end.isoformat(),
            "open": is_in_window(today, cur_adv_start, cur_adv_end),
            "already_paid": cur_advance_paid,
        },
        "final_window": {
            "start": prev_final_start.isoformat(),
            "end": prev_final_end.isoformat(),
            "open": is_in_window(today, prev_final_start, prev_final_end),
            "already_paid": prev_paid,
            # Q6 label flip
            "has_advance": SalaryRecord.objects.filter(
                period_start=prev_period_start,
                period_end=prev_period_end,
                kind=SalaryRecord.SalaryKind.ADVANCE,
            ).exists(),
        },
        "previous_unpaid_banner": prev_overdue,
    }
