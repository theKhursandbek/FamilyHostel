"""
Unit tests — Salary Calculation Engine (Step 18).

Covers:
    - Basic shift-based salary
    - Income bonus via IncomeRule
    - Cleaning bonus (per-room mode)
    - Director fixed salary + admin income
    - Penalty deductions
    - No shifts → zero salary
    - Partial data / edge cases
    - Multiple roles (director who also works shifts)
    - SalaryRecord persistence
    - Helper functions independently
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.admin_panel.models import SystemSettings
from apps.bookings.models import Booking
from apps.cleaning.models import CleaningTask
from apps.payments.models import IncomeRule, SalaryRecord
from apps.reports.models import Penalty
from apps.staff.models import Attendance, ShiftAssignment
from apps.staff.salary_service import (
    calculate_income_bonus,
    calculate_salary,
    calculate_salary_breakdown,
    count_completed_cleaning_tasks,
    count_valid_shifts,
    get_branch_income,
    get_system_settings,
    get_total_penalties,
)

from conftest import (
    AccountFactory,
    BookingFactory,
    BranchFactory,
    ClientFactory,
    DirectorFactory,
    RoomFactory,
    StaffFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_START = datetime.date(2026, 3, 1)
PERIOD_END = datetime.date(2026, 3, 31)


def _create_settings(
    *,
    shift_rate: Decimal = Decimal("100000"),
    per_room_rate: Decimal = Decimal("15000"),
    salary_mode: str = "shift",
) -> SystemSettings:
    """Create or update the singleton SystemSettings."""
    settings, _ = SystemSettings.objects.update_or_create(
        pk=1,
        defaults={
            "shift_rate": shift_rate,
            "per_room_rate": per_room_rate,
            "salary_mode": salary_mode,
        },
    )
    return settings


def _add_attendance(
    account, branch, date, shift_type="day", status="present",
) -> Attendance:
    return Attendance.objects.create(
        account=account,
        branch=branch,
        date=date,
        shift_type=shift_type,
        check_in=timezone.now() if status != "absent" else None,
        status=status,
    )


# ===========================================================================
# get_system_settings
# ===========================================================================


@pytest.mark.django_db
class TestGetSystemSettings:
    def test_creates_default_if_missing(self):
        assert SystemSettings.objects.count() == 0
        settings = get_system_settings()
        assert settings.pk == 1
        assert settings.shift_rate == Decimal("0")

    def test_returns_existing(self):
        _create_settings(shift_rate=Decimal("50000"))
        settings = get_system_settings()
        assert settings.shift_rate == Decimal("50000")


# ===========================================================================
# count_valid_shifts
# ===========================================================================


@pytest.mark.django_db
class TestCountValidShifts:
    def test_counts_present_and_late(self):
        account = AccountFactory()
        branch = BranchFactory()
        _add_attendance(account, branch, PERIOD_START, status="present")
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=1), status="late",
        )
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=2), status="absent",
        )
        assert count_valid_shifts(account.pk, PERIOD_START, PERIOD_END) == 2

    def test_ignores_out_of_range(self):
        account = AccountFactory()
        branch = BranchFactory()
        _add_attendance(account, branch, PERIOD_START - datetime.timedelta(days=1))
        assert count_valid_shifts(account.pk, PERIOD_START, PERIOD_END) == 0


# ===========================================================================
# get_branch_income
# ===========================================================================


@pytest.mark.django_db
class TestGetBranchIncome:
    def test_sums_paid_bookings(self):
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("300000"),
            status="paid",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START + datetime.timedelta(days=5),
            final_price=Decimal("200000"), status="paid",
        )
        # Unpaid booking — must be excluded
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START + datetime.timedelta(days=10),
            final_price=Decimal("100000"), status="pending",
        )

        assert get_branch_income(branch.pk, PERIOD_START, PERIOD_END) == Decimal("500000")

    def test_returns_zero_when_no_bookings(self):
        branch = BranchFactory()
        assert get_branch_income(branch.pk, PERIOD_START, PERIOD_END) == Decimal("0")


# ===========================================================================
# calculate_income_bonus
# ===========================================================================


@pytest.mark.django_db
class TestCalculateIncomeBonus:
    def test_applies_matching_rule(self):
        account = AccountFactory()
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        # Create paid booking → income = 500,000
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("500000"),
            status="paid",
        )

        # Income rule: 0–1,000,000 → 5%
        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("1000000"),
            percent=Decimal("5"),
        )

        # Attendance → day shift at this branch
        _add_attendance(account, branch, PERIOD_START, shift_type="day")

        bonus = calculate_income_bonus(account.pk, PERIOD_START, PERIOD_END)
        assert bonus == Decimal("500000") * Decimal("5") / Decimal("100")  # 25,000

    def test_no_matching_rule_returns_zero(self):
        account = AccountFactory()
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("5000000"),
            status="paid",
        )
        # Rule range doesn't cover 5,000,000
        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("1000000"),
            percent=Decimal("5"),
        )
        _add_attendance(account, branch, PERIOD_START, shift_type="day")

        bonus = calculate_income_bonus(account.pk, PERIOD_START, PERIOD_END)
        assert bonus == Decimal("0")

    def test_multiple_branches(self):
        account = AccountFactory()
        branch_a = BranchFactory()
        branch_b = BranchFactory()
        room_a = RoomFactory(branch=branch_a)
        room_b = RoomFactory(branch=branch_b)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room_a, branch=branch_a,
            check_in_date=PERIOD_START, final_price=Decimal("400000"),
            status="paid",
        )
        BookingFactory(
            client=client, room=room_b, branch=branch_b,
            check_in_date=PERIOD_START, final_price=Decimal("600000"),
            status="paid",
        )

        IncomeRule.objects.create(
            branch=branch_a, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("1000000"),
            percent=Decimal("3"),
        )
        IncomeRule.objects.create(
            branch=branch_b, shift_type="night",
            min_income=Decimal("0"), max_income=Decimal("1000000"),
            percent=Decimal("4"),
        )

        _add_attendance(account, branch_a, PERIOD_START, shift_type="day")
        _add_attendance(account, branch_b, PERIOD_START + datetime.timedelta(days=1), shift_type="night")

        bonus = calculate_income_bonus(account.pk, PERIOD_START, PERIOD_END)
        expected = (
            Decimal("400000") * Decimal("3") / Decimal("100")
            + Decimal("600000") * Decimal("4") / Decimal("100")
        )
        assert bonus == expected  # branch_a bonus + branch_b bonus


# ===========================================================================
# count_completed_cleaning_tasks
# ===========================================================================


@pytest.mark.django_db
class TestCountCompletedCleaningTasks:
    def test_counts_completed_in_period(self):
        staff = StaffFactory()
        branch = staff.branch
        room = RoomFactory(branch=branch)

        CleaningTask.objects.create(
            room=room, branch=branch, assigned_to=staff,
            status="completed",
            completed_at=timezone.make_aware(
                datetime.datetime.combine(PERIOD_START, datetime.time(12, 0)),
            ),
        )
        # Not completed — should be excluded
        CleaningTask.objects.create(
            room=RoomFactory(branch=branch), branch=branch, assigned_to=staff,
            status="in_progress",
        )

        count = count_completed_cleaning_tasks(staff.account_id, PERIOD_START, PERIOD_END)
        assert count == 1

    def test_returns_zero_for_non_staff(self):
        account = AccountFactory()
        assert count_completed_cleaning_tasks(account.pk, PERIOD_START, PERIOD_END) == 0


# ===========================================================================
# get_total_penalties
# ===========================================================================


@pytest.mark.django_db
class TestGetTotalPenalties:
    def test_sums_penalties(self):
        account = AccountFactory()

        Penalty.objects.create(
            account=account, type="late", count=2,
            penalty_amount=Decimal("10000"),
        )
        Penalty.objects.create(
            account=account, type="absence", count=1,
            penalty_amount=Decimal("50000"),
        )

        total = get_total_penalties(account.pk, PERIOD_START, PERIOD_END)
        assert total == Decimal("70000")  # 2×10,000 + 1×50,000

    def test_returns_zero_when_no_penalties(self):
        account = AccountFactory()
        assert get_total_penalties(account.pk, PERIOD_START, PERIOD_END) == Decimal("0")


# ===========================================================================
# calculate_salary_breakdown — full integration
# ===========================================================================


@pytest.mark.django_db
class TestCalculateSalaryBreakdown:
    """Test the main breakdown calculator (no DB persistence)."""

    def test_basic_shift_salary(self):
        """shifts × shift_rate, no income bonus, no cleaning, no penalties."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        for day_offset in range(10):
            _add_attendance(
                account, branch,
                PERIOD_START + datetime.timedelta(days=day_offset),
            )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_count"] == 10
        assert breakdown["shift_pay"] == Decimal("1000000")
        assert breakdown["income_bonus"] == Decimal("0")
        assert breakdown["cleaning_bonus"] == Decimal("0")
        assert breakdown["director_fixed"] == Decimal("0")
        assert breakdown["penalties"] == Decimal("0")
        assert breakdown["total"] == Decimal("1000000")

    def test_shift_salary_with_income_bonus(self):
        """Shift pay + income percentage."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        # 5 shifts
        for i in range(5):
            _add_attendance(
                account, branch,
                PERIOD_START + datetime.timedelta(days=i),
                shift_type="day",
            )

        # Branch income = 2,000,000
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("2000000"),
            status="paid",
        )

        # Rule: 0 – 5,000,000 → 3%
        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("5000000"),
            percent=Decimal("3"),
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_pay"] == Decimal("500000")  # 5 × 100,000
        assert breakdown["income_bonus"] == Decimal("60000")  # 2,000,000 × 3%
        assert breakdown["total"] == Decimal("560000")

    def test_per_room_mode_adds_cleaning_bonus(self):
        """In per_room mode, cleaning tasks count toward salary."""
        _create_settings(
            shift_rate=Decimal("80000"),
            per_room_rate=Decimal("15000"),
            salary_mode="per_room",
        )
        staff = StaffFactory()
        branch = staff.branch

        # 3 shifts
        for i in range(3):
            _add_attendance(
                staff.account, branch,
                PERIOD_START + datetime.timedelta(days=i),
            )

        # 4 completed cleaning tasks
        for i in range(4):
            CleaningTask.objects.create(
                room=RoomFactory(branch=branch), branch=branch,
                assigned_to=staff, status="completed",
                completed_at=timezone.make_aware(
                    datetime.datetime.combine(
                        PERIOD_START + datetime.timedelta(days=i),
                        datetime.time(14, 0),
                    ),
                ),
            )

        breakdown = calculate_salary_breakdown(staff.account_id, PERIOD_START, PERIOD_END)

        assert breakdown["shift_pay"] == Decimal("240000")  # 3 × 80,000
        assert breakdown["cleaning_bonus"] == Decimal("60000")  # 4 × 15,000
        assert breakdown["total"] == Decimal("300000")

    def test_shift_mode_ignores_cleaning(self):
        """In shift mode, cleaning tasks do NOT add to salary."""
        _create_settings(
            shift_rate=Decimal("100000"),
            per_room_rate=Decimal("15000"),
            salary_mode="shift",
        )
        staff = StaffFactory()
        branch = staff.branch

        _add_attendance(staff.account, branch, PERIOD_START)

        CleaningTask.objects.create(
            room=RoomFactory(branch=branch), branch=branch,
            assigned_to=staff, status="completed",
            completed_at=timezone.make_aware(
                datetime.datetime.combine(PERIOD_START, datetime.time(14, 0)),
            ),
        )

        breakdown = calculate_salary_breakdown(staff.account_id, PERIOD_START, PERIOD_END)

        assert breakdown["cleaning_bonus"] == Decimal("0")
        assert breakdown["total"] == Decimal("100000")

    def test_penalties_deducted(self):
        """Penalties reduce salary."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        for i in range(5):
            _add_attendance(account, branch, PERIOD_START + datetime.timedelta(days=i))

        Penalty.objects.create(
            account=account, type="late", count=3,
            penalty_amount=Decimal("10000"),
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_pay"] == Decimal("500000")
        assert breakdown["penalties"] == Decimal("30000")
        assert breakdown["total"] == Decimal("470000")

    def test_penalties_cannot_make_salary_negative(self):
        """Salary floor is 0."""
        _create_settings(shift_rate=Decimal("10000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START)

        Penalty.objects.create(
            account=account, type="absence", count=1,
            penalty_amount=Decimal("500000"),
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)
        assert breakdown["total"] == Decimal("0")

    def test_no_shifts_zero_salary(self):
        """No valid attendance → salary = 0."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_count"] == 0
        assert breakdown["total"] == Decimal("0")

    def test_absent_shifts_not_counted(self):
        """Only present/late count; absent is ignored."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START, status="absent")
        _add_attendance(
            account, branch,
            PERIOD_START + datetime.timedelta(days=1), status="present",
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_count"] == 1
        assert breakdown["total"] == Decimal("100000")


# ===========================================================================
# Director salary
# ===========================================================================


@pytest.mark.django_db
class TestDirectorSalary:
    """Director: fixed salary + admin income if working shifts."""

    def test_director_fixed_salary_no_shifts(self):
        """Director with no shifts still gets fixed salary."""
        _create_settings(shift_rate=Decimal("100000"))
        director = DirectorFactory(salary=Decimal("2000000"))

        breakdown = calculate_salary_breakdown(
            director.account_id, PERIOD_START, PERIOD_END,
        )

        assert breakdown["director_fixed"] == Decimal("2000000")
        assert breakdown["shift_count"] == 0
        assert breakdown["total"] == Decimal("2000000")

    def test_director_fixed_plus_shift_income(self):
        """Director working shifts gets fixed + shift pay + income bonus."""
        _create_settings(shift_rate=Decimal("100000"))
        director = DirectorFactory(salary=Decimal("2000000"))
        branch = director.branch
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        # 3 shifts
        for i in range(3):
            _add_attendance(
                director.account, branch,
                PERIOD_START + datetime.timedelta(days=i),
                shift_type="day",
            )

        # Branch income = 1,000,000
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("1000000"),
            status="paid",
        )

        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("5000000"),
            percent=Decimal("5"),
        )

        breakdown = calculate_salary_breakdown(
            director.account_id, PERIOD_START, PERIOD_END,
        )

        assert breakdown["director_fixed"] == Decimal("2000000")
        assert breakdown["shift_pay"] == Decimal("300000")  # 3 × 100,000
        assert breakdown["income_bonus"] == Decimal("50000")  # 1,000,000 × 5%
        assert breakdown["total"] == Decimal("2350000")

    def test_director_penalties_applied(self):
        """Director salary reduced by penalties but never below 0."""
        _create_settings(shift_rate=Decimal("100000"))
        director = DirectorFactory(salary=Decimal("2000000"))

        Penalty.objects.create(
            account=director.account, type="late", count=5,
            penalty_amount=Decimal("20000"),
        )

        breakdown = calculate_salary_breakdown(
            director.account_id, PERIOD_START, PERIOD_END,
        )

        assert breakdown["total"] == Decimal("1900000")  # 2,000,000 - 100,000


# ===========================================================================
# calculate_salary — persistence
# ===========================================================================


@pytest.mark.django_db
class TestCalculateSalary:
    """Test that calculate_salary creates a SalaryRecord."""

    def test_creates_salary_record(self):
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        for i in range(5):
            _add_attendance(account, branch, PERIOD_START + datetime.timedelta(days=i))

        record = calculate_salary(account.pk, PERIOD_START, PERIOD_END)

        assert isinstance(record, SalaryRecord)
        assert record.pk is not None
        assert record.account.pk == account.pk
        assert record.amount == Decimal("500000")
        assert record.period_start == PERIOD_START
        assert record.period_end == PERIOD_END
        assert record.status == "pending"

    def test_creates_zero_salary_record_for_no_shifts(self):
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()

        record = calculate_salary(account.pk, PERIOD_START, PERIOD_END)

        assert record.amount == Decimal("0")

    def test_multiple_salary_records_allowed(self):
        """Different periods can each produce a record."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START)

        r1 = calculate_salary(account.pk, PERIOD_START, PERIOD_END)
        r2 = calculate_salary(
            account.pk,
            datetime.date(2026, 4, 1),
            datetime.date(2026, 4, 30),
        )

        assert SalaryRecord.objects.filter(account=account).count() == 2
        assert r1.pk != r2.pk


# ===========================================================================
# Complex / edge cases
# ===========================================================================


@pytest.mark.django_db
class TestEdgeCases:
    """Miscellaneous edge-case scenarios."""

    def test_full_formula_all_components(self):
        """
        Shift pay + income bonus + cleaning bonus (per_room mode) - penalties.
        """
        _create_settings(
            shift_rate=Decimal("100000"),
            per_room_rate=Decimal("20000"),
            salary_mode="per_room",
        )

        staff = StaffFactory()
        branch = staff.branch
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        # 4 shifts (day)
        for i in range(4):
            _add_attendance(
                staff.account, branch,
                PERIOD_START + datetime.timedelta(days=i),
                shift_type="day",
            )

        # Branch income = 3,000,000
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("3000000"),
            status="paid",
        )

        # Income rule: 0–5M → 4%
        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("5000000"),
            percent=Decimal("4"),
        )

        # 3 completed cleaning tasks
        for i in range(3):
            CleaningTask.objects.create(
                room=RoomFactory(branch=branch), branch=branch,
                assigned_to=staff, status="completed",
                completed_at=timezone.make_aware(
                    datetime.datetime.combine(
                        PERIOD_START + datetime.timedelta(days=i),
                        datetime.time(14, 0),
                    ),
                ),
            )

        # 1 penalty
        Penalty.objects.create(
            account=staff.account, type="late", count=1,
            penalty_amount=Decimal("10000"),
        )

        breakdown = calculate_salary_breakdown(
            staff.account_id, PERIOD_START, PERIOD_END,
        )

        shift_pay = Decimal("400000")   # 4 × 100,000
        income_bonus = Decimal("120000")  # 3,000,000 × 4%
        cleaning_bonus = Decimal("60000")  # 3 × 20,000
        penalties = Decimal("10000")

        assert breakdown["shift_pay"] == shift_pay
        assert breakdown["income_bonus"] == income_bonus
        assert breakdown["cleaning_bonus"] == cleaning_bonus
        assert breakdown["penalties"] == penalties
        assert breakdown["total"] == shift_pay + income_bonus + cleaning_bonus - penalties

    def test_late_attendance_counts_as_shift(self):
        """Late (>30 min) still counts as a valid shift for salary."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START, status="late")

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)
        assert breakdown["shift_count"] == 1
        assert breakdown["total"] == Decimal("100000")

    def test_mixed_statuses(self):
        """present + late + absent → only present+late counted."""
        _create_settings(shift_rate=Decimal("50000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START, status="present")
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=1), status="late",
        )
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=2), status="absent",
        )
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=3), status="present",
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)
        assert breakdown["shift_count"] == 3
        assert breakdown["total"] == Decimal("150000")

    def test_partial_data_no_income_rules(self):
        """Shifts exist but no IncomeRule → income_bonus is 0."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()

        _add_attendance(account, branch, PERIOD_START)

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)
        assert breakdown["income_bonus"] == Decimal("0")
        assert breakdown["total"] == Decimal("100000")

    def test_multiple_shifts_different_types(self):
        """Account works both day and night shifts at the same branch."""
        _create_settings(shift_rate=Decimal("100000"))
        account = AccountFactory()
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        _add_attendance(account, branch, PERIOD_START, shift_type="day")
        _add_attendance(
            account, branch, PERIOD_START + datetime.timedelta(days=1),
            shift_type="night",
        )

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=PERIOD_START, final_price=Decimal("1000000"),
            status="paid",
        )

        IncomeRule.objects.create(
            branch=branch, shift_type="day",
            min_income=Decimal("0"), max_income=Decimal("5000000"),
            percent=Decimal("3"),
        )
        IncomeRule.objects.create(
            branch=branch, shift_type="night",
            min_income=Decimal("0"), max_income=Decimal("5000000"),
            percent=Decimal("2"),
        )

        breakdown = calculate_salary_breakdown(account.pk, PERIOD_START, PERIOD_END)

        assert breakdown["shift_pay"] == Decimal("200000")
        # Day: 1M × 3% = 30,000, Night: 1M × 2% = 20,000
        assert breakdown["income_bonus"] == Decimal("50000")
        assert breakdown["total"] == Decimal("250000")
