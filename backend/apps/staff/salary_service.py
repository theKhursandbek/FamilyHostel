"""
Salary Calculation Engine (README Section 26.2 & Step 18, REFACTOR_PLAN_2026_04 §5.1).

Per-role rate resolution
------------------------
- **Staff**         → `Staff.salary_override` else `SystemSettings.staff_shift_rate`.
- **Administrator** → `Administrator.salary_override` else `SystemSettings.admin_shift_rate`.
- **Director**      → `Director.salary_override` else `SystemSettings.director_fixed_salary`.
                       Plus a GM bonus = `settings.gm_bonus_percent × full_director_salary`
                       when `Director.is_general_manager=True`.

Formula
-------
salary =
    (number_of_valid_shifts × per_shift_rate)             # staff & admin
  + Σ (branch_income × percent from matching IncomeRule)  # admin & director
  + (completed_cleaning_tasks × per_room_rate, if salary_mode == "per_room")
  + director_fixed                                        # director only
  + gm_bonus                                              # GM director only
  - total_penalties

Constraints
-----------
- Only attendance with status ``present`` or ``late`` counts as a valid shift.
- Only bookings with status ``paid`` contribute to branch income.
- No valid shifts → salary = 0 (except directors, who keep their fixed salary).
- Salary can never go below 0.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TypedDict

from django.db.models import Q, Sum

from apps.accounts.models import Administrator, Director, Staff
from apps.admin_panel.models import SystemSettings
from apps.bookings.models import Booking
from apps.cleaning.models import CleaningTask
from apps.payments.models import IncomeRule, SalaryRecord
from apps.reports.models import Penalty, SalaryAdjustment
from apps.staff.models import Attendance

__all__ = [
    "calculate_salary",
    "calculate_salary_breakdown",
    "get_system_settings",
    "count_valid_shifts",
    "get_branch_income",
    "calculate_income_bonus",
    "count_completed_cleaning_tasks",
    "get_total_penalties",
    "get_monthly_adjustment_totals",
    "resolve_per_shift_rate",
    "resolve_director_payout",
]


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------


class SalaryBreakdown(TypedDict):
    shift_count: int
    shift_pay: Decimal
    income_bonus: Decimal
    cleaning_bonus: Decimal
    director_fixed: Decimal
    gm_bonus: Decimal
    penalties: Decimal
    adjustment_penalty: Decimal
    adjustment_bonus_plus: Decimal
    total: Decimal


# ---------------------------------------------------------------------------
# Helper: system settings singleton
# ---------------------------------------------------------------------------


def get_system_settings() -> SystemSettings:
    """Return the single ``SystemSettings`` row, creating it with defaults if absent."""
    settings, _created = SystemSettings.objects.get_or_create(pk=1)
    return settings


# ---------------------------------------------------------------------------
# Helper: valid shift count
# ---------------------------------------------------------------------------


def count_valid_shifts(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> int:
    """
    Count attendance records with status **present** or **late**.

    Absent records are excluded.  Partial shifts count as full (README rule).
    """
    return Attendance.objects.filter(
        account_id=account_id,
        date__gte=period_start,
        date__lte=period_end,
        status__in=[
            Attendance.AttendanceStatus.PRESENT,
            Attendance.AttendanceStatus.LATE,
        ],
    ).count()


# ---------------------------------------------------------------------------
# Helper: branch income (paid bookings only)
# ---------------------------------------------------------------------------


def get_branch_income(
    branch_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> Decimal:
    """
    Total ``final_price`` of **paid** bookings at *branch* whose
    ``check_in_date`` falls within the given period.
    """
    result = Booking.objects.filter(
        branch_id=branch_id,
        status=Booking.BookingStatus.PAID,
        check_in_date__gte=period_start,
        check_in_date__lte=period_end,
    ).aggregate(total=Sum("final_price"))
    return result["total"] or Decimal("0")


# ---------------------------------------------------------------------------
# Helper: income bonus from IncomeRule
# ---------------------------------------------------------------------------


def calculate_income_bonus(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> Decimal:
    """
    For each branch + shift_type combination the account worked (valid
    attendance), look up the matching ``IncomeRule`` and add
    ``branch_income × percent / 100``.
    """
    valid_qs = Attendance.objects.filter(
        account_id=account_id,
        date__gte=period_start,
        date__lte=period_end,
        status__in=[
            Attendance.AttendanceStatus.PRESENT,
            Attendance.AttendanceStatus.LATE,
        ],
    )

    # .order_by() clears the model's default ordering ("-date") which would
    # otherwise leak into the SELECT DISTINCT and produce duplicate combos.
    combos = (
        valid_qs
        .order_by("branch_id", "shift_type")
        .values("branch_id", "shift_type")
        .distinct()
    )
    bonus = Decimal("0")

    for combo in combos:
        branch_id = combo["branch_id"]
        shift_type = combo["shift_type"]

        income = get_branch_income(branch_id, period_start, period_end)
        if income <= 0:
            continue

        rule = IncomeRule.objects.filter(
            branch_id=branch_id,
            shift_type=shift_type,
            min_income__lte=income,
            max_income__gte=income,
        ).first()

        if rule:
            bonus += income * rule.percent / Decimal("100")

    return bonus


# ---------------------------------------------------------------------------
# Helper: completed cleaning tasks
# ---------------------------------------------------------------------------


def count_completed_cleaning_tasks(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> int:
    """
    Count ``CleaningTask`` records assigned to the account's staff profile
    that were completed within the period.
    """
    from apps.accounts.models import Staff

    try:
        staff = Staff.objects.get(account_id=account_id)
    except Staff.DoesNotExist:
        return 0

    return CleaningTask.objects.filter(
        assigned_to=staff,
        status=CleaningTask.TaskStatus.COMPLETED,
        completed_at__date__gte=period_start,
        completed_at__date__lte=period_end,
    ).count()


# ---------------------------------------------------------------------------
# Helper: total penalties
# ---------------------------------------------------------------------------


def get_total_penalties(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> Decimal:
    """Sum of ``penalty_amount × count`` for penalties in the period."""
    penalties = Penalty.objects.filter(
        account_id=account_id,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    )

    total = Decimal("0")
    for p in penalties:
        total += p.penalty_amount * p.count
    return total


def get_monthly_adjustment_totals(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> tuple[Decimal, Decimal]:
    """Return ``(penalty_total, bonus_plus_total)`` from
    :class:`apps.reports.models.SalaryAdjustment` rows whose
    ``(year, month)`` falls inside the given period.

    REFACTOR_PLAN_2026_04 §3.7 / §3.8 — these adjustments must flow
    through the salary engine alongside the per-event :class:`Penalty`
    rows.
    """
    # The adjustment rows are keyed by (year, month) — convert the period
    # into the set of (year, month) tuples that fall inside it. In practice
    # the period is always one calendar month, but we support arbitrary
    # ranges defensively.
    months: set[tuple[int, int]] = set()
    cur = datetime.date(period_start.year, period_start.month, 1)
    while cur <= period_end:
        months.add((cur.year, cur.month))
        if cur.month == 12:
            cur = datetime.date(cur.year + 1, 1, 1)
        else:
            cur = datetime.date(cur.year, cur.month + 1, 1)

    if not months:
        return Decimal("0"), Decimal("0")

    q = Q()
    for y, m in months:
        q |= Q(year=y, month=m)

    rows = (
        SalaryAdjustment.objects
        .filter(q, account_id=account_id)
        .values("kind")
        .annotate(total=Sum("amount"))
    )
    penalty_total = Decimal("0")
    bonus_plus_total = Decimal("0")
    for row in rows:
        if row["kind"] == SalaryAdjustment.Kind.PENALTY:
            penalty_total = row["total"] or Decimal("0")
        elif row["kind"] == SalaryAdjustment.Kind.BONUS_PLUS:
            bonus_plus_total = row["total"] or Decimal("0")
    return penalty_total, bonus_plus_total


# ---------------------------------------------------------------------------
# Main: calculate_salary
# ---------------------------------------------------------------------------


def resolve_per_shift_rate(account_id: int, settings: SystemSettings) -> Decimal:
    """
    Look up the per-shift rate for *account_id* honouring per-person
    overrides.

    Resolution order (per REFACTOR_PLAN_2026_04 §5.1):

      1. Administrator profile → ``Administrator.salary_override`` else
         ``settings.admin_shift_rate``.
      2. Staff profile         → ``Staff.salary_override`` else
         ``settings.staff_shift_rate``.
      3. Fallback (no admin/staff profile but has attendance, e.g. legacy
         accounts) → ``settings.staff_shift_rate``. Preserves pre-Phase-2
         behaviour.

    Administrator wins over Staff if (somehow) both exist.
    """
    admin = Administrator.objects.filter(account_id=account_id).first()
    if admin is not None:
        return Decimal(admin.salary_override or settings.admin_shift_rate)

    staff = Staff.objects.filter(account_id=account_id).first()
    if staff is not None:
        return Decimal(staff.salary_override or settings.staff_shift_rate)

    # Legacy fallback: account has no role profile but earned shifts.
    return Decimal(settings.staff_shift_rate)


def resolve_director_payout(
    director: Director, settings: SystemSettings,
) -> tuple[Decimal, Decimal]:
    """
    Return ``(fixed_salary, gm_bonus)`` for *director* using the rules from
    REFACTOR_PLAN_2026_04 §5.1:

    - Fixed salary = ``director.salary_override`` else
      ``settings.director_fixed_salary``.
    - GM bonus = ``settings.gm_bonus_percent / 100 × fixed_salary`` when
      ``director.is_general_manager`` is True; else 0.
    """
    fixed = Decimal(director.salary_override or settings.director_fixed_salary)
    gm_bonus = Decimal("0")
    if director.is_general_manager:
        pct = Decimal(settings.gm_bonus_percent or 0)
        gm_bonus = fixed * pct / Decimal("100")
    return fixed, gm_bonus


def calculate_salary(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> SalaryRecord:
    """
    Calculate salary for *account_id* over ``[period_start, period_end]``
    and persist it as a :class:`SalaryRecord`.

    Returns the saved ``SalaryRecord`` instance.  The full breakdown is
    available via :func:`calculate_salary_breakdown` if needed.
    """
    breakdown = calculate_salary_breakdown(account_id, period_start, period_end)

    record = SalaryRecord.objects.create(
        account_id=account_id,
        amount=breakdown["total"],
        period_start=period_start,
        period_end=period_end,
    )
    return record


def calculate_salary_breakdown(
    account_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
) -> SalaryBreakdown:
    """
    Pure calculation — returns the breakdown dict without persisting anything.
    Useful for previews and testing.
    """
    settings = get_system_settings()

    # 1. Valid shifts ----------------------------------------------------------
    shift_count = count_valid_shifts(account_id, period_start, period_end)

    # 2. Base shift pay (per-role rate with per-person override) --------------
    per_shift_rate = resolve_per_shift_rate(account_id, settings)
    shift_pay = Decimal(shift_count) * per_shift_rate

    # 3. Income bonus (% of branch income per IncomeRule) ----------------------
    income_bonus = calculate_income_bonus(account_id, period_start, period_end)

    # 4. Cleaning bonus (per-room mode only) -----------------------------------
    cleaning_bonus = Decimal("0")
    if settings.salary_mode == SystemSettings.SalaryMode.PER_ROOM:
        cleaning_count = count_completed_cleaning_tasks(
            account_id, period_start, period_end,
        )
        cleaning_bonus = Decimal(cleaning_count) * settings.per_room_rate

    # 5. Penalties -------------------------------------------------------------
    penalties = get_total_penalties(account_id, period_start, period_end)

    # 5b. Monthly salary adjustments (REFACTOR_PLAN_2026_04 §3.7 / §3.8) ------
    adj_penalty, adj_bonus_plus = get_monthly_adjustment_totals(
        account_id, period_start, period_end,
    )

    # 6. Director fixed salary + GM bonus -------------------------------------
    director_fixed = Decimal("0")
    gm_bonus = Decimal("0")
    director = Director.objects.filter(account_id=account_id).first()
    if director is not None:
        director_fixed, gm_bonus = resolve_director_payout(director, settings)

    # 7. No shifts + not a director → salary is 0 -----------------------------
    if shift_count == 0 and director_fixed == 0:
        return SalaryBreakdown(
            shift_count=0,
            shift_pay=Decimal("0"),
            income_bonus=Decimal("0"),
            cleaning_bonus=Decimal("0"),
            director_fixed=Decimal("0"),
            gm_bonus=Decimal("0"),
            penalties=Decimal("0"),
            adjustment_penalty=Decimal("0"),
            adjustment_bonus_plus=Decimal("0"),
            total=Decimal("0"),
        )

    # 8. Assemble total (never negative) --------------------------------------
    total = (
        shift_pay
        + income_bonus
        + cleaning_bonus
        + director_fixed
        + gm_bonus
        + adj_bonus_plus
        - penalties
        - adj_penalty
    )
    total = max(total, Decimal("0"))

    return SalaryBreakdown(
        shift_count=shift_count,
        shift_pay=shift_pay,
        income_bonus=income_bonus,
        cleaning_bonus=cleaning_bonus,
        director_fixed=director_fixed,
        gm_bonus=gm_bonus,
        penalties=penalties,
        adjustment_penalty=adj_penalty,
        adjustment_bonus_plus=adj_bonus_plus,
        total=total,
    )
