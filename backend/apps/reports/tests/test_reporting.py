"""
Unit tests — Reporting Service & CSV Export (Step 19).

Covers:
    - get_total_revenue: paid/unpaid bookings, empty data, date filtering
    - get_booking_stats: status breakdown, all statuses, empty
    - get_staff_performance: completed tasks per staff, no tasks
    - get_admin_income: payments per admin, no payments
    - get_attendance_report: present/late/absent counts, multiple accounts
    - export_to_csv: single dict, list of dicts, custom headers, empty, output arg
"""

from __future__ import annotations

import datetime
import io
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.bookings.models import Booking
from apps.cleaning.models import CleaningTask
from apps.payments.models import Payment
from apps.reports.csv_export import export_to_csv
from apps.reports.reporting_service import (
    get_admin_income,
    get_attendance_report,
    get_booking_stats,
    get_staff_performance,
    get_total_revenue,
)
from apps.staff.models import Attendance

from conftest import (
    AccountFactory,
    AdministratorFactory,
    BookingFactory,
    BranchFactory,
    ClientFactory,
    RoomFactory,
    StaffFactory,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_FROM = datetime.date(2026, 4, 1)
DATE_TO = datetime.date(2026, 4, 30)


# ===========================================================================
# get_total_revenue
# ===========================================================================


@pytest.mark.django_db
class TestGetTotalRevenue:
    """Revenue = SUM(final_price) of PAID bookings only."""

    def test_sums_paid_bookings(self):
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, final_price=Decimal("300000"),
            status="paid",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM + datetime.timedelta(days=5),
            final_price=Decimal("200000"), status="paid",
        )

        result = get_total_revenue(branch.pk, DATE_FROM, DATE_TO)

        assert result["total_revenue"] == Decimal("500000")
        assert result["booking_count"] == 2
        assert result["branch_id"] == branch.pk

    def test_excludes_unpaid_bookings(self):
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, final_price=Decimal("500000"),
            status="pending",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM + datetime.timedelta(days=1),
            final_price=Decimal("100000"), status="canceled",
        )

        result = get_total_revenue(branch.pk, DATE_FROM, DATE_TO)

        assert result["total_revenue"] == Decimal("0")
        assert result["booking_count"] == 0

    def test_filters_by_date_range(self):
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        # Inside range
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, final_price=Decimal("100000"),
            status="paid",
        )
        # Outside range
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM - datetime.timedelta(days=1),
            final_price=Decimal("999999"), status="paid",
        )

        result = get_total_revenue(branch.pk, DATE_FROM, DATE_TO)
        assert result["total_revenue"] == Decimal("100000")

    def test_returns_zero_for_empty_branch(self):
        branch = BranchFactory()
        result = get_total_revenue(branch.pk, DATE_FROM, DATE_TO)

        assert result["total_revenue"] == Decimal("0")
        assert result["booking_count"] == 0


# ===========================================================================
# get_booking_stats
# ===========================================================================


@pytest.mark.django_db
class TestGetBookingStats:
    """Counts bookings grouped by status."""

    def test_counts_by_status(self):
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, status="pending",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM + datetime.timedelta(days=1), status="paid",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM + datetime.timedelta(days=2), status="paid",
        )
        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM + datetime.timedelta(days=3), status="canceled",
        )

        result = get_booking_stats(branch.pk, DATE_FROM, DATE_TO)

        assert result["total"] == 4
        assert result["pending"] == 1
        assert result["paid"] == 2
        assert result["canceled"] == 1

    def test_empty_branch(self):
        branch = BranchFactory()
        result = get_booking_stats(branch.pk, DATE_FROM, DATE_TO)

        assert result["total"] == 0
        assert result["pending"] == 0
        assert result["paid"] == 0
        assert result["canceled"] == 0


# ===========================================================================
# get_staff_performance
# ===========================================================================


@pytest.mark.django_db
class TestGetStaffPerformance:
    """Completed cleaning tasks per staff."""

    def test_counts_completed_per_staff(self):
        branch = BranchFactory()
        staff_a = StaffFactory(branch=branch)
        staff_b = StaffFactory(branch=branch)

        ts = timezone.make_aware(
            datetime.datetime.combine(DATE_FROM, datetime.time(12, 0)),
        )

        # Staff A: 3 completed
        for _ in range(3):
            CleaningTask.objects.create(
                room=RoomFactory(branch=branch), branch=branch,
                assigned_to=staff_a, status="completed", completed_at=ts,
            )
        # Staff B: 1 completed
        CleaningTask.objects.create(
            room=RoomFactory(branch=branch), branch=branch,
            assigned_to=staff_b, status="completed", completed_at=ts,
        )
        # Incomplete task — should be excluded
        CleaningTask.objects.create(
            room=RoomFactory(branch=branch), branch=branch,
            assigned_to=staff_a, status="in_progress",
        )

        result = get_staff_performance(branch.pk, DATE_FROM, DATE_TO)

        assert len(result) == 2
        assert result[0]["staff_id"] == staff_a.pk
        assert result[0]["completed_count"] == 3
        assert result[1]["staff_id"] == staff_b.pk
        assert result[1]["completed_count"] == 1

    def test_no_tasks_returns_empty(self):
        branch = BranchFactory()
        result = get_staff_performance(branch.pk, DATE_FROM, DATE_TO)
        assert result == []

    def test_excludes_unassigned_tasks(self):
        branch = BranchFactory()
        ts = timezone.make_aware(
            datetime.datetime.combine(DATE_FROM, datetime.time(12, 0)),
        )
        CleaningTask.objects.create(
            room=RoomFactory(branch=branch), branch=branch,
            assigned_to=None, status="completed", completed_at=ts,
        )

        result = get_staff_performance(branch.pk, DATE_FROM, DATE_TO)
        assert result == []


# ===========================================================================
# get_admin_income
# ===========================================================================


@pytest.mark.django_db
class TestGetAdminIncome:
    """Paid payments grouped by administrator."""

    def test_sums_per_admin(self):
        branch = BranchFactory()
        admin_a = AdministratorFactory(branch=branch)
        admin_b = AdministratorFactory(branch=branch)
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        booking = BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, status="paid",
        )

        Payment.objects.create(
            booking=booking, amount=Decimal("300000"),
            payment_type="manual", is_paid=True, created_by=admin_a,
        )
        Payment.objects.create(
            booking=booking, amount=Decimal("200000"),
            payment_type="manual", is_paid=True, created_by=admin_a,
        )
        Payment.objects.create(
            booking=booking, amount=Decimal("150000"),
            payment_type="manual", is_paid=True, created_by=admin_b,
        )

        result = get_admin_income(branch.pk, DATE_FROM, DATE_TO)

        assert len(result) == 2
        # Sorted by total_collected desc
        assert result[0]["admin_id"] == admin_a.pk
        assert result[0]["total_collected"] == Decimal("500000")
        assert result[0]["payment_count"] == 2
        assert result[1]["admin_id"] == admin_b.pk
        assert result[1]["total_collected"] == Decimal("150000")

    def test_excludes_unpaid_payments(self):
        branch = BranchFactory()
        admin = AdministratorFactory(branch=branch)
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        booking = BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, status="pending",
        )
        Payment.objects.create(
            booking=booking, amount=Decimal("100000"),
            payment_type="manual", is_paid=False, created_by=admin,
        )

        result = get_admin_income(branch.pk, DATE_FROM, DATE_TO)
        assert result == []

    def test_no_payments_returns_empty(self):
        branch = BranchFactory()
        result = get_admin_income(branch.pk, DATE_FROM, DATE_TO)
        assert result == []


# ===========================================================================
# get_attendance_report
# ===========================================================================


@pytest.mark.django_db
class TestGetAttendanceReport:
    """Present / late / absent counts per account."""

    def test_counts_statuses(self):
        branch = BranchFactory()
        account = AccountFactory()

        for i, status in enumerate(["present", "present", "late", "absent"]):
            Attendance.objects.create(
                account=account, branch=branch,
                date=DATE_FROM + datetime.timedelta(days=i),
                shift_type="day", status=status,
                check_in=timezone.now() if status != "absent" else None,
            )

        result = get_attendance_report(branch.pk, DATE_FROM, DATE_TO)

        assert len(result) == 1
        row = result[0]
        assert row["account_id"] == account.pk
        assert row["present"] == 2
        assert row["late"] == 1
        assert row["absent"] == 1
        assert row["total"] == 4

    def test_multiple_accounts(self):
        branch = BranchFactory()
        acc_a = AccountFactory()
        acc_b = AccountFactory()

        for i in range(5):
            Attendance.objects.create(
                account=acc_a, branch=branch,
                date=DATE_FROM + datetime.timedelta(days=i),
                shift_type="day", status="present", check_in=timezone.now(),
            )
        for i in range(2):
            Attendance.objects.create(
                account=acc_b, branch=branch,
                date=DATE_FROM + datetime.timedelta(days=i),
                shift_type="day", status="late", check_in=timezone.now(),
            )

        result = get_attendance_report(branch.pk, DATE_FROM, DATE_TO)

        assert len(result) == 2
        # Sorted by total desc
        assert result[0]["account_id"] == acc_a.pk
        assert result[0]["total"] == 5
        assert result[1]["account_id"] == acc_b.pk
        assert result[1]["total"] == 2

    def test_empty_returns_empty_list(self):
        branch = BranchFactory()
        result = get_attendance_report(branch.pk, DATE_FROM, DATE_TO)
        assert result == []


# ===========================================================================
# CSV Export
# ===========================================================================


class TestExportToCsv:
    """Tests for the generic CSV export utility."""

    def test_list_of_dicts(self):
        data = [
            {"name": "Alice", "score": 90},
            {"name": "Bob", "score": 85},
        ]
        csv_text = export_to_csv(data)
        lines = csv_text.strip().split("\r\n")

        assert lines[0] == "name,score"
        assert lines[1] == "Alice,90"
        assert lines[2] == "Bob,85"

    def test_single_dict_treated_as_one_row(self):
        data = {"branch_id": 1, "total_revenue": Decimal("500000")}
        csv_text = export_to_csv(data)
        lines = csv_text.strip().split("\r\n")

        assert len(lines) == 2  # header + 1 row
        assert "branch_id" in lines[0]
        assert "500000" in lines[1]

    def test_custom_headers(self):
        data = [{"a": 1, "b": 2, "c": 3}]
        csv_text = export_to_csv(data, headers=["a", "c"])
        lines = csv_text.strip().split("\r\n")

        assert lines[0] == "a,c"
        assert lines[1] == "1,3"

    def test_empty_data_returns_empty_string(self):
        assert export_to_csv([]) == ""

    def test_output_parameter(self):
        data = [{"x": 10}]
        buf = io.StringIO()
        csv_text = export_to_csv(data, output=buf)

        assert buf.getvalue() == csv_text
        assert "x" in csv_text

    @pytest.mark.django_db
    def test_integration_with_revenue_report(self):
        """CSV export works end-to-end with a real report."""
        branch = BranchFactory()
        room = RoomFactory(branch=branch)
        client = ClientFactory()

        BookingFactory(
            client=client, room=room, branch=branch,
            check_in_date=DATE_FROM, final_price=Decimal("750000"),
            status="paid",
        )

        report = get_total_revenue(branch.pk, DATE_FROM, DATE_TO)
        csv_text = export_to_csv(report)
        lines = csv_text.strip().split("\r\n")

        assert "total_revenue" in lines[0]
        assert "750000" in lines[1]

    @pytest.mark.django_db
    def test_integration_with_staff_performance(self):
        """CSV export works end-to-end with a list-based report."""
        branch = BranchFactory()
        staff = StaffFactory(branch=branch)
        ts = timezone.make_aware(
            datetime.datetime.combine(DATE_FROM, datetime.time(12, 0)),
        )

        for _ in range(2):
            CleaningTask.objects.create(
                room=RoomFactory(branch=branch), branch=branch,
                assigned_to=staff, status="completed", completed_at=ts,
            )

        report = get_staff_performance(branch.pk, DATE_FROM, DATE_TO)
        csv_text = export_to_csv(report)
        lines = csv_text.strip().split("\r\n")

        assert "staff_name" in lines[0]
        assert "2" in lines[1]  # completed_count
