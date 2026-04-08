"""
Tests for Step 21.7 — Director system workflows.

Covers:
    Penalty Management:
        - Service layer (create, update, delete, audit)
        - API endpoints (POST, GET, PATCH, DELETE)
        - Permission enforcement (director CRUD, staff view own)

    Facility Logs:
        - Service layer (create, update, audit)
        - API endpoints (POST, GET, PATCH)
        - Permission enforcement (director+)

    Monthly Reports:
        - API endpoints (GET list, POST generate)
        - Report generation with aggregated data
        - Permission enforcement (director+)

    Director Task Assignment:
        - Service layer (director_assign_task, reassignment, audit)
        - API endpoint (POST /cleaning/tasks/{id}/assign/ with staff_id)
        - Permission enforcement
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status

from apps.cleaning.models import CleaningTask
from apps.cleaning.services import create_cleaning_task, director_assign_task
from apps.reports.facility_service import create_facility_log, update_facility_log
from apps.reports.models import AuditLog, FacilityLog, MonthlyReport, Penalty
from apps.reports.penalty_service import create_penalty, delete_penalty, update_penalty
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

# Base URLs
PENALTY_URL = "/api/v1/penalties/"
FACILITY_URL = "/api/v1/facility-logs/"
MONTHLY_URL = "/api/v1/reports/monthly/"
CLEANING_URL = "/api/v1/cleaning/tasks/"


# ==============================================================================
# PENALTY — SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestPenaltyService:
    """Test the penalty service layer."""

    def test_create_penalty(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            reason="Late to shift",
            created_by=director.account,
            performed_by=director.account,
        )
        assert penalty.pk is not None
        assert penalty.type == "late"
        assert penalty.penalty_amount == Decimal("10000")
        assert penalty.reason == "Late to shift"
        assert penalty.created_by == director.account

    def test_create_penalty_audit_log(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        create_penalty(
            account=staff.account,
            penalty_type="absence",
            penalty_amount=Decimal("50000"),
            created_by=director.account,
            performed_by=director.account,
        )
        audit = AuditLog.objects.filter(action="penalty.created").first()
        assert audit is not None
        assert audit.entity_type == "Penalty"

    def test_update_penalty(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        updated = update_penalty(
            penalty=penalty,
            performed_by=director.account,
            penalty_amount=Decimal("20000"),
            reason="Updated reason",
        )
        assert updated.penalty_amount == Decimal("20000")
        assert updated.reason == "Updated reason"

    def test_update_penalty_audit(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        update_penalty(
            penalty=penalty, performed_by=director.account,
            reason="Changed",
        )
        audit = AuditLog.objects.filter(action="penalty.updated").first()
        assert audit is not None
        assert audit.before_data is not None
        assert audit.after_data is not None

    def test_delete_penalty(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        penalty_id = penalty.pk
        delete_penalty(penalty=penalty, performed_by=director.account)
        assert not Penalty.objects.filter(pk=penalty_id).exists()

    def test_delete_penalty_audit(self, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        delete_penalty(penalty=penalty, performed_by=director.account)
        audit = AuditLog.objects.filter(action="penalty.deleted").first()
        assert audit is not None
        assert audit.before_data is not None


# ==============================================================================
# PENALTY — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestPenaltyAPI:
    """Test penalty REST endpoints."""

    def test_create_penalty(self, director_client, director_profile, branch):
        staff = StaffFactory(branch=branch)
        resp = director_client.post(PENALTY_URL, {
            "account": staff.account.pk,
            "type": "late",
            "penalty_amount": "10000.00",
            "reason": "Late by 30 min",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["type"] == "late"
        assert resp.data["penalty_amount"] == "10000.00"
        assert resp.data["reason"] == "Late by 30 min"

    def test_create_penalty_invalid_account(self, director_client):
        resp = director_client.post(PENALTY_URL, {
            "account": 99999,
            "type": "late",
            "penalty_amount": "10000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_penalty_invalid_type(self, director_client, branch):
        staff = StaffFactory(branch=branch)
        resp = director_client.post(PENALTY_URL, {
            "account": staff.account.pk,
            "type": "invalid",
            "penalty_amount": "10000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_penalties_director(self, director_client, director_profile, branch):
        staff = StaffFactory(branch=branch)
        create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director_profile.account,
        )
        resp = director_client.get(PENALTY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_list_penalties_staff_sees_own(self, staff_client, staff_profile, branch):
        director = DirectorFactory(branch=branch)
        create_penalty(
            account=staff_profile.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        # Create another penalty for a different staff
        other_staff = StaffFactory(branch=branch)
        create_penalty(
            account=other_staff.account,
            penalty_type="absence",
            penalty_amount=Decimal("50000"),
            created_by=director.account,
        )
        resp = staff_client.get(PENALTY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["account"] == staff_profile.account.pk

    def test_update_penalty(self, director_client, director_profile, branch):
        staff = StaffFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director_profile.account,
        )
        resp = director_client.patch(
            f"{PENALTY_URL}{penalty.pk}/",
            {"penalty_amount": "25000.00", "reason": "Revised"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["penalty_amount"] == "25000.00"
        assert resp.data["reason"] == "Revised"

    def test_delete_penalty(self, director_client, director_profile, branch):
        staff = StaffFactory(branch=branch)
        penalty = create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director_profile.account,
        )
        resp = director_client.delete(f"{PENALTY_URL}{penalty.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Penalty.objects.filter(pk=penalty.pk).exists()

    def test_staff_cannot_create_penalty(self, staff_client, staff_profile, branch):
        other_staff = StaffFactory(branch=branch)
        resp = staff_client.post(PENALTY_URL, {
            "account": other_staff.account.pk,
            "type": "late",
            "penalty_amount": "10000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_staff_cannot_delete_penalty(self, staff_client, staff_profile, branch):
        director = DirectorFactory(branch=branch)
        penalty = create_penalty(
            account=staff_profile.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        resp = staff_client.delete(f"{PENALTY_URL}{penalty.pk}/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(PENALTY_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_superadmin_sees_all(self, superadmin_client, branch):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        create_penalty(
            account=staff.account,
            penalty_type="late",
            penalty_amount=Decimal("10000"),
            created_by=director.account,
        )
        resp = superadmin_client.get(PENALTY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1


# ==============================================================================
# FACILITY LOG — SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestFacilityLogService:
    """Test the facility log service layer."""

    def test_create_facility_log(self, branch):
        director = DirectorFactory(branch=branch)
        log = create_facility_log(
            branch=branch,
            facility_type="repair",
            description="Broken door lock",
            cost=Decimal("150000"),
            performed_by=director.account,
        )
        assert log.pk is not None
        assert log.type == "repair"
        assert log.status == "open"
        assert log.cost == Decimal("150000")

    def test_create_facility_log_audit(self, branch):
        director = DirectorFactory(branch=branch)
        create_facility_log(
            branch=branch,
            facility_type="water",
            description="Pipe leak",
            performed_by=director.account,
        )
        audit = AuditLog.objects.filter(action="facility_log.created").first()
        assert audit is not None

    def test_update_facility_log(self, branch):
        director = DirectorFactory(branch=branch)
        log = create_facility_log(
            branch=branch,
            facility_type="water",
            description="Pipe leak",
            performed_by=director.account,
        )
        updated = update_facility_log(
            facility_log=log,
            performed_by=director.account,
            status="resolved",
            description="Pipe leak — fixed",
        )
        assert updated.status == "resolved"
        assert updated.description == "Pipe leak — fixed"

    def test_update_facility_log_audit(self, branch):
        director = DirectorFactory(branch=branch)
        log = create_facility_log(
            branch=branch,
            facility_type="gas",
            description="Gas smell",
            performed_by=director.account,
        )
        update_facility_log(
            facility_log=log,
            performed_by=director.account,
            status="resolved",
        )
        audit = AuditLog.objects.filter(action="facility_log.updated").first()
        assert audit is not None
        assert audit.before_data is not None
        assert audit.after_data is not None
        assert audit.before_data["status"] == "open"
        assert audit.after_data["status"] == "resolved"


# ==============================================================================
# FACILITY LOG — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestFacilityLogAPI:
    """Test facility log REST endpoints."""

    def test_create_facility_log(self, director_client, director_profile, branch):
        resp = director_client.post(FACILITY_URL, {
            "type": "electricity",
            "description": "Power outage on 2nd floor",
            "cost": "200000.00",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["type"] == "electricity"
        assert resp.data["status"] == "open"

    def test_create_facility_log_with_branch(
        self, director_client, director_profile, branch,
    ):
        resp = director_client.post(FACILITY_URL, {
            "branch": branch.pk,
            "type": "gas",
            "description": "Gas pipe issue",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["branch"] == branch.pk

    def test_list_facility_logs(self, director_client, director_profile, branch):
        create_facility_log(
            branch=branch,
            facility_type="repair",
            description="Fix door",
            performed_by=director_profile.account,
        )
        resp = director_client.get(FACILITY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_update_facility_log(self, director_client, director_profile, branch):
        log = create_facility_log(
            branch=branch,
            facility_type="water",
            description="Leaking pipe",
            performed_by=director_profile.account,
        )
        resp = director_client.patch(
            f"{FACILITY_URL}{log.pk}/",
            {"status": "resolved"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "resolved"

    def test_filter_by_status(self, director_client, director_profile, branch):
        create_facility_log(
            branch=branch, facility_type="water",
            description="Leak", performed_by=director_profile.account,
        )
        log2 = create_facility_log(
            branch=branch, facility_type="gas",
            description="Gas", performed_by=director_profile.account,
        )
        update_facility_log(
            facility_log=log2, performed_by=director_profile.account,
            status="resolved",
        )
        resp = director_client.get(FACILITY_URL, {"status": "open"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["type"] == "water"

    def test_staff_forbidden(self, staff_client):
        resp = staff_client.get(FACILITY_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_forbidden(self, admin_client):
        resp = admin_client.get(FACILITY_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(FACILITY_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# MONTHLY REPORT — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestMonthlyReportAPI:
    """Test monthly report REST endpoints."""

    def test_generate_report(self, director_client, director_profile, branch):
        resp = director_client.post(
            f"{MONTHLY_URL}generate/",
            {"month": 3, "year": 2026},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["month"] == 3
        assert resp.data["year"] == 2026
        assert resp.data["branch"] == branch.pk
        assert "summary_data" in resp.data

    def test_generate_report_includes_revenue(
        self, director_client, director_profile, branch,
    ):
        resp = director_client.post(
            f"{MONTHLY_URL}generate/",
            {"month": 3, "year": 2026},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        summary = resp.data["summary_data"]
        assert "revenue" in summary
        assert "bookings" in summary
        assert "penalties" in summary
        assert "facility_issues" in summary

    def test_regenerate_updates_report(
        self, director_client, director_profile, branch,
    ):
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 1, "year": 2026})
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 1, "year": 2026})
        # Should still be only one report (update_or_create)
        assert MonthlyReport.objects.filter(
            branch=branch, month=1, year=2026,
        ).count() == 1

    def test_list_reports(self, director_client, director_profile, branch):
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 1, "year": 2026})
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 2, "year": 2026})
        resp = director_client.get(MONTHLY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 2

    def test_retrieve_report(self, director_client, director_profile, branch):
        resp_gen = director_client.post(
            f"{MONTHLY_URL}generate/", {"month": 3, "year": 2026},
        )
        report_id = resp_gen.data["id"]
        resp = director_client.get(f"{MONTHLY_URL}{report_id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == report_id

    def test_generate_report_audit(self, director_client, director_profile, branch):
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 3, "year": 2026})
        audit = AuditLog.objects.filter(
            action="monthly_report.generated",
        ).first()
        assert audit is not None
        assert audit.entity_type == "MonthlyReport"

    def test_filter_by_year(self, director_client, director_profile, branch):
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 1, "year": 2025})
        director_client.post(f"{MONTHLY_URL}generate/", {"month": 1, "year": 2026})
        resp = director_client.get(MONTHLY_URL, {"year": 2026})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["year"] == 2026

    def test_staff_forbidden(self, staff_client):
        resp = staff_client.get(MONTHLY_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(MONTHLY_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_month(self, director_client, director_profile):
        resp = director_client.post(
            f"{MONTHLY_URL}generate/", {"month": 13, "year": 2026},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_superadmin_sees_all(self, superadmin_client, director_profile, branch):
        from apps.reports.monthly_service import generate_monthly_report

        generate_monthly_report(
            branch=branch, month=3, year=2026, created_by=director_profile,
        )
        resp = superadmin_client.get(MONTHLY_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1


# ==============================================================================
# DIRECTOR TASK ASSIGNMENT — SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestDirectorAssignTaskService:
    """Test the director task assignment service."""

    def test_director_assign_pending_task(self, branch, room):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        assigned = director_assign_task(
            task=task,
            staff_profile=staff,
            performed_by=director.account,
        )
        assert assigned.assigned_to == staff
        assert assigned.status == CleaningTask.TaskStatus.IN_PROGRESS

    def test_director_reassign_in_progress(self, branch, room):
        staff1 = StaffFactory(branch=branch)
        staff2 = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        director_assign_task(
            task=task, staff_profile=staff1, performed_by=director.account,
        )
        reassigned = director_assign_task(
            task=task, staff_profile=staff2, performed_by=director.account,
        )
        assert reassigned.assigned_to == staff2

    def test_director_cannot_assign_completed(self, branch, room):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        task.status = CleaningTask.TaskStatus.COMPLETED
        task.save()
        with pytest.raises(DjangoValidationError, match="Cannot assign a completed"):
            director_assign_task(
                task=task, staff_profile=staff, performed_by=director.account,
            )

    def test_director_assign_audit(self, branch, room):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        director_assign_task(
            task=task, staff_profile=staff, performed_by=director.account,
        )
        audit = AuditLog.objects.filter(
            action="cleaning_task.director_assigned",
        ).first()
        assert audit is not None
        assert audit.before_data is not None
        assert audit.after_data is not None
        assert audit.before_data["assigned_to_id"] is None
        assert audit.after_data["assigned_to_id"] == staff.pk


# ==============================================================================
# DIRECTOR TASK ASSIGNMENT — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestDirectorAssignTaskAPI:
    """Test the director assign endpoint via the API."""

    def test_director_assign_via_api(self, director_client, director_profile, branch, room):
        staff = StaffFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director_profile.account,
        )
        resp = director_client.post(
            f"{CLEANING_URL}{task.pk}/assign/",
            {"staff_id": staff.pk},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["assigned_to"] == staff.pk
        assert resp.data["status"] == "in_progress"

    def test_director_reassign_via_api(self, director_client, director_profile, branch, room):
        staff1 = StaffFactory(branch=branch)
        staff2 = StaffFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director_profile.account,
        )
        director_client.post(
            f"{CLEANING_URL}{task.pk}/assign/", {"staff_id": staff1.pk},
        )
        resp = director_client.post(
            f"{CLEANING_URL}{task.pk}/assign/", {"staff_id": staff2.pk},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["assigned_to"] == staff2.pk

    def test_director_assign_invalid_staff(
        self, director_client, director_profile, branch, room,
    ):
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director_profile.account,
        )
        resp = director_client.post(
            f"{CLEANING_URL}{task.pk}/assign/", {"staff_id": 99999},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_staff_self_assign_still_works(self, staff_client, staff_profile, branch, room):
        """Backward compatibility: staff self-assign without staff_id."""
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        resp = staff_client.post(f"{CLEANING_URL}{task.pk}/assign/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["assigned_to"] == staff_profile.pk

    def test_staff_cannot_assign_others(self, staff_client, staff_profile, branch, room):
        """Staff sending staff_id should be rejected (not director)."""
        other_staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)
        task = create_cleaning_task(
            room=room, branch=branch, performed_by=director.account,
        )
        resp = staff_client.post(
            f"{CLEANING_URL}{task.pk}/assign/", {"staff_id": other_staff.pk},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
