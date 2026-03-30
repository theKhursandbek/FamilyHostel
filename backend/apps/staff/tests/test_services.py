"""
Unit tests — Staff/Attendance service layer.
"""

import datetime
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.staff.models import Attendance, ShiftAssignment
from apps.staff.services import check_in, check_out, create_shift_assignment, mark_absent

from conftest import AccountFactory, DirectorFactory


@pytest.mark.django_db
class TestCheckIn:
    """Tests for check_in()."""

    def test_on_time_check_in(self, staff_profile, branch):
        """Check-in within 30 minutes of shift start -> PRESENT."""
        today = datetime.date.today()
        fake_now = timezone.make_aware(
            datetime.datetime.combine(today, datetime.time(8, 15)),
        )
        with patch("apps.staff.services.timezone.now", return_value=fake_now):
            attendance = check_in(
                account=staff_profile.account,
                branch=branch,
                date=today,
                shift_type="day",
            )
        assert attendance.status == "present"
        assert attendance.check_in is not None

    def test_late_check_in(self, staff_profile, branch):
        """Check-in > 30 minutes after shift start -> LATE."""
        today = datetime.date.today()
        fake_now = timezone.make_aware(
            datetime.datetime.combine(today, datetime.time(8, 45)),
        )
        with patch("apps.staff.services.timezone.now", return_value=fake_now):
            attendance = check_in(
                account=staff_profile.account,
                branch=branch,
                date=today,
                shift_type="day",
            )
        assert attendance.status == "late"

    def test_no_double_check_in(self, staff_profile, branch):
        today = datetime.date.today()
        check_in(
            account=staff_profile.account,
            branch=branch,
            date=today,
            shift_type="day",
        )
        with pytest.raises(ValidationError, match="Already checked in"):
            check_in(
                account=staff_profile.account,
                branch=branch,
                date=today,
                shift_type="day",
            )


@pytest.mark.django_db
class TestCheckOut:
    """Tests for check_out()."""

    def test_check_out_after_check_in(self, staff_profile, branch):
        today = datetime.date.today()
        attendance = check_in(
            account=staff_profile.account,
            branch=branch,
            date=today,
            shift_type="day",
        )
        result = check_out(attendance)
        assert result.check_out is not None

    def test_cannot_check_out_without_check_in(self, branch, staff_profile):
        attendance = mark_absent(
            account=staff_profile.account,
            branch=branch,
            date=datetime.date.today(),
            shift_type="day",
        )
        with pytest.raises(ValidationError, match="without checking in"):
            check_out(attendance)


@pytest.mark.django_db
class TestMarkAbsent:
    """Tests for mark_absent()."""

    def test_creates_absent_record(self, staff_profile, branch):
        today = datetime.date.today()
        attendance = mark_absent(
            account=staff_profile.account,
            branch=branch,
            date=today,
            shift_type="day",
        )
        assert attendance.status == "absent"
        assert attendance.check_in is None


@pytest.mark.django_db
class TestShiftAssignment:
    """Tests for create_shift_assignment()."""

    def test_creates_assignment(self, account, branch, director_profile):
        assignment = create_shift_assignment(
            account=account,
            role="staff",
            branch=branch,
            shift_type="day",
            date=datetime.date.today(),
            assigned_by=director_profile,
        )
        assert assignment.pk is not None

    def test_one_admin_per_shift_per_branch(self, branch, director_profile):
        acc1 = AccountFactory()
        acc2 = AccountFactory()
        today = datetime.date.today()
        create_shift_assignment(
            account=acc1,
            role="admin",
            branch=branch,
            shift_type="day",
            date=today,
            assigned_by=director_profile,
        )
        with pytest.raises(ValidationError, match="already assigned"):
            create_shift_assignment(
                account=acc2,
                role="admin",
                branch=branch,
                shift_type="day",
                date=today,
                assigned_by=director_profile,
            )
