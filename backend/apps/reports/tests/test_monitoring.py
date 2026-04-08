"""
Tests for SuperAdmin monitoring — AuditLog & SuspiciousActivity endpoints.

Covers:
    Audit Log API:
        - List with filtering (action, entity_type, role, date range)
        - Retrieve single entry
        - Director sees only branch-scoped logs
        - SuperAdmin sees all logs
        - Staff/Admin forbidden
        - Unauthenticated forbidden

    Suspicious Activity API:
        - List with filtering (activity_type, is_blocked, ip_address)
        - Retrieve single entry
        - SuperAdmin only
        - Director/Staff/Admin forbidden
        - Unauthenticated forbidden
"""

from __future__ import annotations

import pytest
from rest_framework import status

from apps.accounts.models import SuspiciousActivity
from apps.reports.models import AuditLog
from apps.reports.services import log_action
from conftest import (
    AdministratorFactory,
    BranchFactory,
    DirectorFactory,
    StaffFactory,
    SuperAdminFactory,
)

AUDIT_URL = "/api/v1/audit-logs/"
SUSPICIOUS_URL = "/api/v1/suspicious-activities/"


# ==============================================================================
# HELPERS
# ==============================================================================


def _create_audit_log(account, *, action="test.action", entity_type="TestEntity"):
    """Create an audit log entry directly for testing."""
    return AuditLog.objects.create(
        account=account,
        role=account.role if hasattr(account, "role") else "unknown",
        action=action,
        entity_type=entity_type,
        entity_id=1,
        before_data={"key": "before"},
        after_data={"key": "after"},
    )


def _create_suspicious_activity(
    *,
    ip_address="192.168.1.100",
    activity_type="failed_login",
    account=None,
    is_blocked=False,
):
    return SuspiciousActivity.objects.create(
        account=account,
        ip_address=ip_address,
        activity_type=activity_type,
        count=3,
        is_blocked=is_blocked,
    )


# ==============================================================================
# AUDIT LOG — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestAuditLogAPI:
    """Test the audit log browsing endpoints."""

    def test_superadmin_lists_all_audit_logs(
        self, superadmin_client, superadmin_profile, branch,
    ):
        staff = StaffFactory(branch=branch)
        director = DirectorFactory(branch=branch)

        _create_audit_log(staff.account, action="staff.checkin")
        _create_audit_log(director.account, action="report.generate")
        _create_audit_log(superadmin_profile.account, action="system.config")

        resp = superadmin_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 3

    def test_superadmin_retrieves_single_audit_log(
        self, superadmin_client, superadmin_profile,
    ):
        log = _create_audit_log(superadmin_profile.account, action="test.retrieve")
        resp = superadmin_client.get(f"{AUDIT_URL}{log.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["action"] == "test.retrieve"
        assert resp.data["before_data"] == {"key": "before"}
        assert resp.data["after_data"] == {"key": "after"}

    def test_superadmin_filter_by_action(
        self, superadmin_client, superadmin_profile,
    ):
        _create_audit_log(superadmin_profile.account, action="penalty.created")
        _create_audit_log(superadmin_profile.account, action="booking.created")

        resp = superadmin_client.get(AUDIT_URL, {"action": "penalty.created"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["action"] == "penalty.created"

    def test_superadmin_filter_by_entity_type(
        self, superadmin_client, superadmin_profile,
    ):
        _create_audit_log(
            superadmin_profile.account,
            action="test.a", entity_type="Penalty",
        )
        _create_audit_log(
            superadmin_profile.account,
            action="test.b", entity_type="Booking",
        )

        resp = superadmin_client.get(AUDIT_URL, {"entity_type": "Penalty"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1

    def test_superadmin_filter_by_role(
        self, superadmin_client, superadmin_profile, branch,
    ):
        staff = StaffFactory(branch=branch)
        _create_audit_log(superadmin_profile.account, action="a")
        log2 = AuditLog.objects.create(
            account=staff.account,
            role="staff",
            action="b",
            entity_type="Test",
        )

        resp = superadmin_client.get(AUDIT_URL, {"role": "staff"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == log2.pk

    def test_director_sees_only_branch_logs(
        self, director_client, director_profile, branch,
    ):
        # In-branch staff
        staff = StaffFactory(branch=branch)
        _create_audit_log(staff.account, action="staff.action")
        _create_audit_log(director_profile.account, action="director.action")

        # Out-of-branch staff
        other_branch = BranchFactory()
        other_staff = StaffFactory(branch=other_branch)
        _create_audit_log(other_staff.account, action="other.action")

        resp = director_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_200_OK
        # Should see 2 (in-branch staff + director itself), not the other branch
        assert resp.data["count"] == 2

    def test_director_cannot_see_other_branch_log_detail(
        self, director_client, branch,
    ):
        other_branch = BranchFactory()
        other_staff = StaffFactory(branch=other_branch)
        log = _create_audit_log(other_staff.account, action="hidden")

        resp = director_client.get(f"{AUDIT_URL}{log.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_forbidden(self, staff_client):
        resp = staff_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_forbidden(self, admin_client):
        resp = admin_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_includes_account_email(
        self, superadmin_client, superadmin_profile,
    ):
        _create_audit_log(superadmin_profile.account, action="test.email")
        resp = superadmin_client.get(AUDIT_URL)
        assert resp.status_code == status.HTTP_200_OK
        entry = resp.data["results"][0]
        assert "account_email" in entry

    def test_audit_log_via_log_action_service(
        self, superadmin_client, superadmin_profile,
    ):
        """Verify that logs created via the log_action service appear in the API."""
        log_action(
            account=superadmin_profile.account,
            action="service.test",
            entity_type="TestModel",
            entity_id=42,
            before_data={"status": "old"},
            after_data={"status": "new"},
        )

        resp = superadmin_client.get(AUDIT_URL, {"action": "service.test"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["entity_id"] == 42
        assert resp.data["results"][0]["after_data"]["status"] == "new"


# ==============================================================================
# SUSPICIOUS ACTIVITY — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestSuspiciousActivityAPI:
    """Test the suspicious activity browsing endpoints."""

    def test_superadmin_lists_all(self, superadmin_client):
        _create_suspicious_activity(ip_address="10.0.0.1")
        _create_suspicious_activity(ip_address="10.0.0.2")

        resp = superadmin_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 2

    def test_superadmin_retrieves_single(self, superadmin_client):
        sa = _create_suspicious_activity(
            ip_address="192.168.1.1",
            activity_type="rate_limit_exceeded",
        )

        resp = superadmin_client.get(f"{SUSPICIOUS_URL}{sa.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["ip_address"] == "192.168.1.1"
        assert resp.data["activity_type"] == "rate_limit_exceeded"
        assert resp.data["count"] == 3

    def test_filter_by_activity_type(self, superadmin_client):
        _create_suspicious_activity(activity_type="failed_login")
        _create_suspicious_activity(activity_type="unauthorized_access")

        resp = superadmin_client.get(
            SUSPICIOUS_URL, {"activity_type": "failed_login"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["activity_type"] == "failed_login"

    def test_filter_by_is_blocked(self, superadmin_client):
        _create_suspicious_activity(ip_address="10.0.0.1", is_blocked=False)
        _create_suspicious_activity(ip_address="10.0.0.2", is_blocked=True)

        resp = superadmin_client.get(SUSPICIOUS_URL, {"is_blocked": True})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["is_blocked"] is True

    def test_filter_by_ip_address(self, superadmin_client):
        _create_suspicious_activity(ip_address="172.16.0.1")
        _create_suspicious_activity(ip_address="172.16.0.2")

        resp = superadmin_client.get(
            SUSPICIOUS_URL, {"ip_address": "172.16.0.1"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1

    def test_response_includes_account_email(
        self, superadmin_client, superadmin_profile,
    ):
        _create_suspicious_activity(account=superadmin_profile.account)

        resp = superadmin_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_200_OK
        entry = resp.data["results"][0]
        assert "account_email" in entry

    def test_anonymous_activity_has_null_account(self, superadmin_client):
        _create_suspicious_activity(account=None)

        resp = superadmin_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_200_OK
        entry = resp.data["results"][0]
        assert entry["account"] is None
        assert entry["account_email"] is None

    def test_director_forbidden(self, director_client):
        resp = director_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_forbidden(self, staff_client):
        resp = staff_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_forbidden(self, admin_client):
        resp = admin_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(SUSPICIOUS_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
