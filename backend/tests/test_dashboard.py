"""
Tests for Step 21.3 — Dashboard APIs.

Covers:
    - Dashboard service functions (admin, director, super admin)
    - API endpoint access & response format
    - Permission enforcement (role-based access)
    - Data correctness with real model data
    - Edge cases (no data, multiple branches)
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin_panel.dashboard_service import (
    get_admin_dashboard,
    get_director_dashboard,
    get_super_admin_dashboard,
)
from apps.admin_panel.models import CashSession
from apps.bookings.models import Booking
from apps.branches.models import Room
from apps.cleaning.models import CleaningTask
from apps.payments.models import Payment
from apps.staff.models import Attendance, ShiftAssignment
from conftest import (
    AccountFactory,
    AdministratorFactory,
    BookingFactory,
    BranchFactory,
    ClientFactory,
    DirectorFactory,
    RoomFactory,
    RoomTypeFactory,
    StaffFactory,
    SuperAdminFactory,
)


# ==============================================================================
# HELPERS
# ==============================================================================

ADMIN_URL = "/api/v1/dashboard/admin/"
DIRECTOR_URL = "/api/v1/dashboard/director/"
SUPERADMIN_URL = "/api/v1/dashboard/super-admin/"


@pytest.fixture
def _branch_with_data(db):
    """Create a branch with rooms, bookings, payments, cleaning tasks, etc."""
    branch = BranchFactory()
    room_type = RoomTypeFactory()
    rooms = [
        RoomFactory(branch=branch, room_type=room_type, status="available"),
        RoomFactory(branch=branch, room_type=room_type, status="occupied"),
        RoomFactory(branch=branch, room_type=room_type, status="booked"),
    ]

    client = ClientFactory()

    # Bookings
    b1 = BookingFactory(
        client=client, room=rooms[0], branch=branch,
        status="paid", final_price=Decimal("500000"),
    )
    b2 = BookingFactory(
        client=client, room=rooms[1], branch=branch,
        status="pending", final_price=Decimal("300000"),
    )

    # Payment (paid today)
    Payment.objects.create(
        booking=b1,
        amount=Decimal("500000"),
        payment_type="manual",
        is_paid=True,
        paid_at=timezone.now(),
    )

    # Staff & cleaning tasks
    staff = StaffFactory(branch=branch)
    task = CleaningTask.objects.create(
        room=rooms[0], branch=branch,
        status="completed",
        assigned_to=staff,
        completed_at=timezone.now(),
    )

    # Admin, director
    admin = AdministratorFactory(branch=branch)
    director = DirectorFactory(branch=branch)

    # Shift assignment
    ShiftAssignment.objects.create(
        account=admin.account,
        role="admin",
        branch=branch,
        shift_type="day",
        date=timezone.localdate(),
        assigned_by=director,
    )

    # Attendance
    Attendance.objects.create(
        account=staff.account,
        branch=branch,
        date=timezone.localdate(),
        shift_type="day",
        status="present",
    )

    # Cash session
    CashSession.objects.create(
        admin=admin,
        branch=branch,
        shift_type="day",
        start_time=timezone.now() - timedelta(hours=2),
        opening_balance=Decimal("1000000"),
    )

    return {
        "branch": branch,
        "rooms": rooms,
        "admin": admin,
        "director": director,
        "staff": staff,
        "bookings": [b1, b2],
        "task": task,
    }


# ==============================================================================
# SERVICE TESTS — get_admin_dashboard()
# ==============================================================================


@pytest.mark.django_db
class TestAdminDashboardService:
    """Test get_admin_dashboard() returns correct data."""

    def test_returns_branch_info(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert data["branch"]["id"] == _branch_with_data["branch"].pk
        assert data["branch"]["name"] == _branch_with_data["branch"].name

    def test_returns_current_shift(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert data["current_shift"] is not None
        assert data["current_shift"]["shift_type"] == "day"

    def test_returns_bookings_today(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert data["bookings_today"]["total"] == 2
        assert data["bookings_today"]["paid"] == 1
        assert data["bookings_today"]["pending"] == 1

    def test_returns_revenue_today(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert Decimal(data["revenue_today"]) == Decimal("500000")

    def test_returns_active_rooms(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert data["active_rooms"]["total"] == 3
        assert data["active_rooms"]["available"] == 1
        assert data["active_rooms"]["occupied"] == 1
        assert data["active_rooms"]["booked"] == 1

    def test_returns_cash_session(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        data = get_admin_dashboard(admin.account)
        assert data["cash_session"] is not None
        assert data["cash_session"]["shift_type"] == "day"

    def test_empty_dashboard(self, db):
        """Admin with no activity gets zeroed dashboard."""
        branch = BranchFactory()
        admin = AdministratorFactory(branch=branch)
        data = get_admin_dashboard(admin.account)
        assert data["bookings_today"]["total"] == 0
        assert data["revenue_today"] == "0"
        assert data["current_shift"] is None
        assert data["cash_session"] is None


# ==============================================================================
# SERVICE TESTS — get_director_dashboard()
# ==============================================================================


@pytest.mark.django_db
class TestDirectorDashboardService:
    """Test get_director_dashboard() returns correct data."""

    def test_returns_revenue(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        data = get_director_dashboard(branch)
        assert Decimal(data["revenue"]["today"]) == Decimal("500000")
        assert Decimal(data["revenue"]["month"]) >= Decimal("500000")

    def test_returns_booking_stats(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        data = get_director_dashboard(branch)
        assert data["booking_stats"]["today"]["total"] == 2
        assert data["booking_stats"]["month"]["total"] >= 2

    def test_returns_staff_performance(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        data = get_director_dashboard(branch)
        assert len(data["staff_performance"]) == 1
        assert data["staff_performance"][0]["tasks_completed"] == 1

    def test_returns_attendance_summary(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        data = get_director_dashboard(branch)
        assert data["attendance_summary"]["total"] == 1
        assert data["attendance_summary"]["present"] == 1

    def test_returns_pending_issues(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        data = get_director_dashboard(branch)
        assert data["pending_issues"]["cleaning_retries"] == 0
        assert data["pending_issues"]["pending_cleaning"] == 0

    def test_with_retry_tasks(self, _branch_with_data):
        branch = _branch_with_data["branch"]
        room = RoomFactory(branch=branch, room_type=RoomTypeFactory())
        CleaningTask.objects.create(
            room=room, branch=branch, status="retry_required",
        )
        data = get_director_dashboard(branch)
        assert data["pending_issues"]["cleaning_retries"] == 1

    def test_empty_branch(self, db):
        branch = BranchFactory()
        data = get_director_dashboard(branch)
        assert data["revenue"]["today"] == "0"
        assert data["booking_stats"]["today"]["total"] == 0
        assert data["staff_performance"] == []
        assert data["attendance_summary"]["total"] == 0


# ==============================================================================
# SERVICE TESTS — get_super_admin_dashboard()
# ==============================================================================


@pytest.mark.django_db
class TestSuperAdminDashboardService:
    """Test get_super_admin_dashboard() returns correct data."""

    def test_returns_branches(self, _branch_with_data):
        data = get_super_admin_dashboard()
        assert data["branches"]["total"] >= 1
        assert data["branches"]["active"] >= 1

    def test_returns_revenue(self, _branch_with_data):
        data = get_super_admin_dashboard()
        assert Decimal(data["revenue"]["today"]) >= Decimal("500000")

    def test_returns_top_branch(self, _branch_with_data):
        data = get_super_admin_dashboard()
        assert data["top_branch"] is not None
        assert data["top_branch"]["id"] == _branch_with_data["branch"].pk

    def test_returns_personnel(self, _branch_with_data):
        data = get_super_admin_dashboard()
        assert data["personnel"]["active_staff"] >= 1
        assert data["personnel"]["active_admins"] >= 1

    def test_returns_system_activity(self, _branch_with_data):
        data = get_super_admin_dashboard()
        assert data["system_activity"]["bookings_today"] >= 2
        assert data["system_activity"]["cleaning_today"]["completed"] >= 1

    def test_no_data(self, db):
        data = get_super_admin_dashboard()
        assert data["branches"]["total"] == 0
        assert data["revenue"]["today"] == "0"
        assert data["top_branch"] is None
        assert data["personnel"]["active_staff"] == 0

    def test_includes_security_blocks(self, db):
        data = get_super_admin_dashboard()
        assert "active_security_blocks" in data["system_activity"]
        assert data["system_activity"]["active_security_blocks"] == 0


# ==============================================================================
# API ENDPOINT TESTS — Admin Dashboard
# ==============================================================================


@pytest.mark.django_db
class TestAdminDashboardEndpoint:
    """GET /api/v1/dashboard/admin/"""

    def test_admin_can_access(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        client = APIClient()
        client.force_authenticate(user=admin.account)
        response = client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["branch"]["id"] == _branch_with_data["branch"].pk

    def test_response_wrapped_in_success(self, _branch_with_data):
        admin = _branch_with_data["admin"]
        client = APIClient()
        client.force_authenticate(user=admin.account)
        response = client.get(ADMIN_URL)
        body = response.json()
        assert body["success"] is True
        assert "data" in body

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_returns_403(self, staff_client):
        response = staff_client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_returns_403(self, api_client, client_profile):
        api_client.force_authenticate(user=client_profile.account)
        response = api_client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_director_without_admin_profile_returns_400(self, director_client):
        response = director_client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_superadmin_without_admin_profile_returns_400(self, superadmin_client):
        response = superadmin_client.get(ADMIN_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# API ENDPOINT TESTS — Director Dashboard
# ==============================================================================


@pytest.mark.django_db
class TestDirectorDashboardEndpoint:
    """GET /api/v1/dashboard/director/"""

    def test_director_can_access(self, _branch_with_data):
        director = _branch_with_data["director"]
        client = APIClient()
        client.force_authenticate(user=director.account)
        response = client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["branch"]["id"] == _branch_with_data["branch"].pk

    def test_response_wrapped_in_success(self, _branch_with_data):
        director = _branch_with_data["director"]
        client = APIClient()
        client.force_authenticate(user=director.account)
        response = client.get(DIRECTOR_URL)
        body = response.json()
        assert body["success"] is True
        assert "data" in body

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_returns_403(self, staff_client):
        response = staff_client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_returns_403(self, admin_client):
        response = admin_client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_returns_403(self, api_client, client_profile):
        api_client.force_authenticate(user=client_profile.account)
        response = api_client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_superadmin_without_branch_id_returns_400(self, superadmin_client):
        response = superadmin_client.get(DIRECTOR_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_superadmin_with_branch_id(self, _branch_with_data, superadmin_client):
        branch = _branch_with_data["branch"]
        response = superadmin_client.get(DIRECTOR_URL, {"branch_id": branch.pk})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["branch"]["id"] == branch.pk

    def test_superadmin_invalid_branch_id_returns_404(self, superadmin_client):
        response = superadmin_client.get(DIRECTOR_URL, {"branch_id": 99999})
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# API ENDPOINT TESTS — Super Admin Dashboard
# ==============================================================================


@pytest.mark.django_db
class TestSuperAdminDashboardEndpoint:
    """GET /api/v1/dashboard/super-admin/"""

    def test_superadmin_can_access(self, superadmin_client, _branch_with_data):
        response = superadmin_client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_200_OK
        assert "branches" in response.data
        assert "revenue" in response.data

    def test_response_wrapped_in_success(self, superadmin_client, _branch_with_data):
        response = superadmin_client.get(SUPERADMIN_URL)
        body = response.json()
        assert body["success"] is True
        assert "data" in body

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_returns_403(self, staff_client):
        response = staff_client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_returns_403(self, admin_client):
        response = admin_client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_director_returns_403(self, director_client):
        response = director_client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_returns_403(self, api_client, client_profile):
        api_client.force_authenticate(user=client_profile.account)
        response = api_client.get(SUPERADMIN_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# DATA CORRECTNESS — multiple branches, isolation
# ==============================================================================


@pytest.mark.django_db
class TestDashboardDataIsolation:
    """Ensure dashboards show only relevant data (no cross-branch leaks)."""

    def test_admin_sees_only_own_branch(self, db):
        branch_a = BranchFactory()
        branch_b = BranchFactory()
        rt = RoomTypeFactory()
        room_a = RoomFactory(branch=branch_a, room_type=rt)
        room_b = RoomFactory(branch=branch_b, room_type=rt)

        client_p = ClientFactory()
        BookingFactory(client=client_p, room=room_a, branch=branch_a, status="paid")
        BookingFactory(client=client_p, room=room_b, branch=branch_b, status="paid")

        admin_a = AdministratorFactory(branch=branch_a)
        data = get_admin_dashboard(admin_a.account)
        assert data["bookings_today"]["total"] == 1  # only branch_a

    def test_director_sees_only_own_branch(self, db):
        branch_a = BranchFactory()
        branch_b = BranchFactory()
        rt = RoomTypeFactory()
        room_a = RoomFactory(branch=branch_a, room_type=rt)
        room_b = RoomFactory(branch=branch_b, room_type=rt)

        client_p = ClientFactory()
        b1 = BookingFactory(client=client_p, room=room_a, branch=branch_a, status="paid")
        b2 = BookingFactory(client=client_p, room=room_b, branch=branch_b, status="paid")

        Payment.objects.create(
            booking=b1, amount=Decimal("100000"),
            payment_type="manual", is_paid=True, paid_at=timezone.now(),
        )
        Payment.objects.create(
            booking=b2, amount=Decimal("200000"),
            payment_type="manual", is_paid=True, paid_at=timezone.now(),
        )

        data_a = get_director_dashboard(branch_a)
        data_b = get_director_dashboard(branch_b)
        assert Decimal(data_a["revenue"]["today"]) == Decimal("100000")
        assert Decimal(data_b["revenue"]["today"]) == Decimal("200000")

    def test_superadmin_sees_all_branches(self, db):
        branch_a = BranchFactory()
        branch_b = BranchFactory()
        rt = RoomTypeFactory()
        room_a = RoomFactory(branch=branch_a, room_type=rt)
        room_b = RoomFactory(branch=branch_b, room_type=rt)

        client_p = ClientFactory()
        b1 = BookingFactory(client=client_p, room=room_a, branch=branch_a, status="paid")
        b2 = BookingFactory(client=client_p, room=room_b, branch=branch_b, status="paid")

        Payment.objects.create(
            booking=b1, amount=Decimal("100000"),
            payment_type="manual", is_paid=True, paid_at=timezone.now(),
        )
        Payment.objects.create(
            booking=b2, amount=Decimal("200000"),
            payment_type="manual", is_paid=True, paid_at=timezone.now(),
        )

        data = get_super_admin_dashboard()
        assert Decimal(data["revenue"]["today"]) == Decimal("300000")
        assert data["branches"]["total"] == 2
