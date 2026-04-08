"""
Tests for Step 21.5 — Day-Off Request system.

Covers:
    - Model validation (date range, clean)
    - Service layer (create, approve, reject, overlap, audit)
    - API endpoints (CRUD, approve/reject actions)
    - Permission enforcement (staff own only, director branch, superadmin all)
    - Edge cases (past dates, already-reviewed, overlapping)
"""

from __future__ import annotations

import datetime

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status

from apps.reports.models import AuditLog
from apps.staff.day_off_service import (
    approve_day_off_request,
    create_day_off_request,
    reject_day_off_request,
)
from apps.staff.models import DayOffRequest
from conftest import (
    AccountFactory,
    AdministratorFactory,
    BranchFactory,
    ClientFactory,
    DirectorFactory,
    StaffFactory,
    SuperAdminFactory,
)

# Base URL for the day-off-request endpoints.
DAY_OFF_URL = "/api/v1/staff/day-off-requests/"


# ==============================================================================
# MODEL TESTS
# ==============================================================================


@pytest.mark.django_db
class TestDayOffRequestModel:
    """Test the DayOffRequest model basics."""

    def test_create_minimal(self):
        staff = StaffFactory()
        req = DayOffRequest.objects.create(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        assert req.status == DayOffRequest.Status.PENDING
        assert req.reviewed_by is None
        assert req.reviewed_at is None

    def test_str_representation(self):
        staff = StaffFactory()
        req = DayOffRequest.objects.create(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date(2026, 5, 1),
            end_date=datetime.date(2026, 5, 3),
        )
        s = str(req)
        assert "2026-05-01" in s
        assert "2026-05-03" in s
        assert "pending" in s

    def test_clean_rejects_end_before_start(self):
        staff = StaffFactory()
        req = DayOffRequest(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date(2026, 5, 5),
            end_date=datetime.date(2026, 5, 3),
        )
        with pytest.raises(DjangoValidationError) as exc_info:
            req.clean()
        assert "end_date" in exc_info.value.message_dict

    def test_ordering_is_newest_first(self):
        staff = StaffFactory()
        DayOffRequest.objects.create(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        DayOffRequest.objects.create(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=5),
            end_date=datetime.date.today() + datetime.timedelta(days=6),
        )
        qs = list(DayOffRequest.objects.all())
        # -created_at ordering: both may share the same created_at,
        # so verify both are returned and newest created_at is first.
        assert len(qs) == 2
        assert qs[0].created_at >= qs[1].created_at


# ==============================================================================
# SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestCreateDayOffRequest:
    """Test create_day_off_request service function."""

    def test_create_success(self):
        staff = StaffFactory()
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=3),
            reason="Family event",
        )
        assert req.pk is not None
        assert req.status == DayOffRequest.Status.PENDING
        assert req.reason == "Family event"

    def test_create_audit_logged(self):
        staff = StaffFactory()
        create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        assert AuditLog.objects.filter(action="day_off_request.created").exists()

    def test_end_before_start_rejected(self):
        staff = StaffFactory()
        with pytest.raises(DjangoValidationError) as exc_info:
            create_day_off_request(
                account=staff.account,
                branch=staff.branch,
                start_date=datetime.date.today() + datetime.timedelta(days=5),
                end_date=datetime.date.today() + datetime.timedelta(days=3),
            )
        assert "end_date" in exc_info.value.message_dict

    def test_past_start_date_rejected(self):
        staff = StaffFactory()
        with pytest.raises(DjangoValidationError) as exc_info:
            create_day_off_request(
                account=staff.account,
                branch=staff.branch,
                start_date=datetime.date.today() - datetime.timedelta(days=1),
                end_date=datetime.date.today() + datetime.timedelta(days=1),
            )
        assert "start_date" in exc_info.value.message_dict

    def test_overlapping_pending_rejected(self):
        staff = StaffFactory()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=3),
        )
        with pytest.raises(DjangoValidationError) as exc_info:
            create_day_off_request(
                account=staff.account,
                branch=staff.branch,
                start_date=tomorrow + datetime.timedelta(days=2),
                end_date=tomorrow + datetime.timedelta(days=5),
            )
        assert "start_date" in exc_info.value.message_dict

    def test_overlapping_approved_rejected(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=3),
        )
        approve_day_off_request(
            day_off_request=req,
            reviewed_by=director,
        )
        with pytest.raises(DjangoValidationError):
            create_day_off_request(
                account=staff.account,
                branch=staff.branch,
                start_date=tomorrow + datetime.timedelta(days=1),
                end_date=tomorrow + datetime.timedelta(days=2),
            )

    def test_non_overlapping_allowed(self):
        staff = StaffFactory()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=1),
        )
        # No overlap: starts after previous ends
        req2 = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow + datetime.timedelta(days=5),
            end_date=tomorrow + datetime.timedelta(days=6),
        )
        assert req2.pk is not None

    def test_rejected_request_does_not_block_overlap(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=3),
        )
        reject_day_off_request(day_off_request=req, reviewed_by=director)
        # Same dates should now be allowed since previous was rejected
        req2 = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=3),
        )
        assert req2.pk is not None


@pytest.mark.django_db
class TestApproveDayOffRequest:
    """Test approve_day_off_request service function."""

    def test_approve_success(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        result = approve_day_off_request(
            day_off_request=req,
            reviewed_by=director,
            comment="Approved. Enjoy!",
        )
        assert result.status == DayOffRequest.Status.APPROVED
        assert result.reviewed_by == director
        assert result.reviewed_at is not None
        assert result.review_comment == "Approved. Enjoy!"

    def test_approve_creates_audit_log(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        approve_day_off_request(day_off_request=req, reviewed_by=director)
        assert AuditLog.objects.filter(action="day_off_request.approved").exists()

    def test_cannot_approve_non_pending(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        approve_day_off_request(day_off_request=req, reviewed_by=director)
        with pytest.raises(DjangoValidationError) as exc_info:
            approve_day_off_request(day_off_request=req, reviewed_by=director)
        assert "status" in exc_info.value.message_dict


@pytest.mark.django_db
class TestRejectDayOffRequest:
    """Test reject_day_off_request service function."""

    def test_reject_success(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        result = reject_day_off_request(
            day_off_request=req,
            reviewed_by=director,
            comment="Sorry, busy period.",
        )
        assert result.status == DayOffRequest.Status.REJECTED
        assert result.review_comment == "Sorry, busy period."

    def test_reject_creates_audit_log(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        reject_day_off_request(day_off_request=req, reviewed_by=director)
        assert AuditLog.objects.filter(action="day_off_request.rejected").exists()

    def test_cannot_reject_non_pending(self):
        staff = StaffFactory()
        director = DirectorFactory(branch=staff.branch)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=datetime.date.today() + datetime.timedelta(days=1),
            end_date=datetime.date.today() + datetime.timedelta(days=2),
        )
        reject_day_off_request(day_off_request=req, reviewed_by=director)
        with pytest.raises(DjangoValidationError) as exc_info:
            reject_day_off_request(day_off_request=req, reviewed_by=director)
        assert "status" in exc_info.value.message_dict


# ==============================================================================
# API ENDPOINT TESTS
# ==============================================================================


@pytest.mark.django_db
class TestDayOffRequestAPI:
    """Test the REST API endpoints for day-off requests."""

    # --- Create ---

    def test_staff_can_create(self, api_client):
        staff = StaffFactory()
        api_client.force_authenticate(user=staff.account)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(tomorrow),
            "end_date": str(tomorrow + datetime.timedelta(days=2)),
            "reason": "Feeling unwell",
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data  # type: ignore[union-attr]
        assert data["status"] == "pending"
        assert data["reason"] == "Feeling unwell"

    def test_admin_can_create(self, api_client):
        admin = AdministratorFactory()
        api_client.force_authenticate(user=admin.account)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(tomorrow),
            "end_date": str(tomorrow),
            "reason": "Personal",
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_client_cannot_create(self, api_client):
        client = ClientFactory()
        api_client.force_authenticate(user=client.account)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(tomorrow),
            "end_date": str(tomorrow),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_create(self, api_client):
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(tomorrow),
            "end_date": str(tomorrow),
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_dates_rejected(self, api_client):
        staff = StaffFactory()
        api_client.force_authenticate(user=staff.account)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(tomorrow + datetime.timedelta(days=3)),
            "end_date": str(tomorrow),
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_past_date_rejected_by_api(self, api_client):
        staff = StaffFactory()
        api_client.force_authenticate(user=staff.account)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        response = api_client.post(DAY_OFF_URL, {
            "start_date": str(yesterday),
            "end_date": str(datetime.date.today()),
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # --- List ---

    def test_staff_sees_own_requests_only(self, api_client):
        staff1 = StaffFactory()
        staff2 = StaffFactory(branch=staff1.branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        create_day_off_request(
            account=staff1.account,
            branch=staff1.branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        create_day_off_request(
            account=staff2.account,
            branch=staff2.branch,
            start_date=tomorrow + datetime.timedelta(days=5),
            end_date=tomorrow + datetime.timedelta(days=6),
        )
        api_client.force_authenticate(user=staff1.account)
        response = api_client.get(DAY_OFF_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        results = data.get("results", data)
        assert len(results) == 1

    def test_director_sees_branch_requests(self, api_client):
        branch = BranchFactory()
        director = DirectorFactory(branch=branch)
        staff1 = StaffFactory(branch=branch)
        other_branch = BranchFactory()
        staff2 = StaffFactory(branch=other_branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        create_day_off_request(
            account=staff1.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        create_day_off_request(
            account=staff2.account,
            branch=other_branch,
            start_date=tomorrow + datetime.timedelta(days=5),
            end_date=tomorrow + datetime.timedelta(days=6),
        )
        api_client.force_authenticate(user=director.account)
        response = api_client.get(DAY_OFF_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        results = data.get("results", data)
        assert len(results) == 1

    def test_superadmin_sees_all(self, api_client):
        superadmin = SuperAdminFactory()
        branch1 = BranchFactory()
        branch2 = BranchFactory()
        staff1 = StaffFactory(branch=branch1)
        staff2 = StaffFactory(branch=branch2)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        create_day_off_request(
            account=staff1.account,
            branch=branch1,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        create_day_off_request(
            account=staff2.account,
            branch=branch2,
            start_date=tomorrow + datetime.timedelta(days=5),
            end_date=tomorrow + datetime.timedelta(days=6),
        )
        api_client.force_authenticate(user=superadmin.account)
        response = api_client.get(DAY_OFF_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        results = data.get("results", data)
        assert len(results) == 2

    # --- Approve ---

    def test_director_can_approve(self, api_client):
        branch = BranchFactory()
        director = DirectorFactory(branch=branch)
        staff = StaffFactory(branch=branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow + datetime.timedelta(days=1),
        )
        api_client.force_authenticate(user=director.account)
        response = api_client.post(
            f"{DAY_OFF_URL}{req.pk}/approve/",
            {"comment": "OK"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        assert data["status"] == "approved"
        assert data["review_comment"] == "OK"

    def test_staff_cannot_approve(self, api_client):
        branch = BranchFactory()
        staff = StaffFactory(branch=branch)
        DirectorFactory(branch=branch)  # ensure director exists
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        api_client.force_authenticate(user=staff.account)
        response = api_client.post(f"{DAY_OFF_URL}{req.pk}/approve/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_approve_already_approved_fails(self, api_client):
        branch = BranchFactory()
        director = DirectorFactory(branch=branch)
        staff = StaffFactory(branch=branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        approve_day_off_request(day_off_request=req, reviewed_by=director)
        api_client.force_authenticate(user=director.account)
        response = api_client.post(f"{DAY_OFF_URL}{req.pk}/approve/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # --- Reject ---

    def test_director_can_reject(self, api_client):
        branch = BranchFactory()
        director = DirectorFactory(branch=branch)
        staff = StaffFactory(branch=branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        api_client.force_authenticate(user=director.account)
        response = api_client.post(
            f"{DAY_OFF_URL}{req.pk}/reject/",
            {"comment": "Busy week"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        assert data["status"] == "rejected"

    def test_staff_cannot_reject(self, api_client):
        branch = BranchFactory()
        staff = StaffFactory(branch=branch)
        DirectorFactory(branch=branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        api_client.force_authenticate(user=staff.account)
        response = api_client.post(f"{DAY_OFF_URL}{req.pk}/reject/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Retrieve ---

    def test_retrieve_own_request(self, api_client):
        staff = StaffFactory()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff.account,
            branch=staff.branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        api_client.force_authenticate(user=staff.account)
        response = api_client.get(f"{DAY_OFF_URL}{req.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_retrieve_others_request(self, api_client):
        staff1 = StaffFactory()
        staff2 = StaffFactory()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req = create_day_off_request(
            account=staff1.account,
            branch=staff1.branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        api_client.force_authenticate(user=staff2.account)
        response = api_client.get(f"{DAY_OFF_URL}{req.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Filter ---

    def test_filter_by_status(self, api_client):
        branch = BranchFactory()
        director = DirectorFactory(branch=branch)
        staff = StaffFactory(branch=branch)
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        req1 = create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow,
            end_date=tomorrow,
        )
        create_day_off_request(
            account=staff.account,
            branch=branch,
            start_date=tomorrow + datetime.timedelta(days=10),
            end_date=tomorrow + datetime.timedelta(days=11),
        )
        approve_day_off_request(day_off_request=req1, reviewed_by=director)

        api_client.force_authenticate(user=director.account)
        response = api_client.get(DAY_OFF_URL, {"status": "approved"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data  # type: ignore[union-attr]
        results = data.get("results", data)
        assert len(results) == 1
        assert results[0]["status"] == "approved"


# ==============================================================================
# URL ROUTING TESTS
# ==============================================================================


class TestDayOffURLRouting:
    """Verify URL routing is correct."""

    def test_endpoints_registered(self):
        from django.urls import reverse

        assert reverse("staff:day-off-request-list") == DAY_OFF_URL
        assert (
            reverse("staff:day-off-request-detail", kwargs={"pk": 1})
            == f"{DAY_OFF_URL}1/"
        )
        assert (
            reverse("staff:day-off-request-approve", kwargs={"pk": 1})
            == f"{DAY_OFF_URL}1/approve/"
        )
        assert (
            reverse("staff:day-off-request-reject", kwargs={"pk": 1})
            == f"{DAY_OFF_URL}1/reject/"
        )
