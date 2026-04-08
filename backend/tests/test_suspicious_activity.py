"""
Tests for Step 21.2 — Suspicious Activity Detection & Protection.

Covers:
    - SuspiciousActivity model creation and constraints
    - Detection service (track, block, auto-recovery, manual reset)
    - BlockedUserMiddleware (rejects blocked IPs/accounts)
    - SecurityLoggingMiddleware integration with detection service
    - End-to-end: repeated failures → auto-block → auto-unblock
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import SuspiciousActivity
from config.security.detection import (
    ACTIVITY_THRESHOLDS,
    BLOCK_DURATION,
    TRACKING_WINDOW,
    get_block_status,
    is_blocked,
    reset_blocks,
    track_suspicious_activity,
)
from conftest import AccountFactory


# ==============================================================================
# MODEL TESTS
# ==============================================================================


@pytest.mark.django_db
class TestSuspiciousActivityModel:
    """Verify model fields, choices, and indexes."""

    def test_create_record(self):
        record = SuspiciousActivity.objects.create(
            ip_address="192.168.1.1",
            activity_type=SuspiciousActivity.ActivityType.FAILED_LOGIN,
        )
        assert record.pk is not None
        assert record.count == 1
        assert record.is_blocked is False
        assert record.blocked_until is None
        assert record.account is None

    def test_activity_type_choices(self):
        choices = [c[0] for c in SuspiciousActivity.ActivityType.choices]
        assert "failed_login" in choices
        assert "rate_limit_exceeded" in choices
        assert "unauthorized_access" in choices
        assert "abnormal_behavior" in choices

    def test_str_tracking(self):
        record = SuspiciousActivity(
            ip_address="10.0.0.1",
            activity_type="failed_login",
            count=3,
            is_blocked=False,
        )
        assert "tracking" in str(record)
        assert "10.0.0.1" in str(record)

    def test_str_blocked(self):
        record = SuspiciousActivity(
            ip_address="10.0.0.2",
            activity_type="rate_limit_exceeded",
            count=10,
            is_blocked=True,
        )
        assert "BLOCKED" in str(record)

    def test_with_account(self, account):
        record = SuspiciousActivity.objects.create(
            ip_address="172.16.0.1",
            activity_type="unauthorized_access",
            account=account,
        )
        assert record.account == account
        assert record in account.suspicious_activities.all()

    def test_db_table_name(self):
        assert SuspiciousActivity._meta.db_table == "suspicious_activities"

    def test_ordering(self):
        assert SuspiciousActivity._meta.ordering == ["-updated_at"]

    def test_indexes_exist(self):
        index_names = [idx.name for idx in SuspiciousActivity._meta.indexes]
        assert "idx_sa_ip_type" in index_names
        assert "idx_sa_blocked" in index_names


# ==============================================================================
# DETECTION SERVICE — track_suspicious_activity()
# ==============================================================================


@pytest.mark.django_db
class TestTrackSuspiciousActivity:
    """Test the core tracking function."""

    def test_first_occurrence_creates_record(self):
        blocked = track_suspicious_activity("1.2.3.4", "failed_login")
        assert blocked is False
        assert SuspiciousActivity.objects.filter(
            ip_address="1.2.3.4", activity_type="failed_login",
        ).exists()

    def test_increments_count_on_repeat(self):
        track_suspicious_activity("1.2.3.4", "failed_login")
        track_suspicious_activity("1.2.3.4", "failed_login")
        record = SuspiciousActivity.objects.get(
            ip_address="1.2.3.4", activity_type="failed_login",
        )
        assert record.count == 2

    def test_blocks_at_threshold(self):
        threshold = ACTIVITY_THRESHOLDS["failed_login"]  # 5
        for i in range(threshold - 1):
            result = track_suspicious_activity("5.5.5.5", "failed_login")
            assert result is False

        # This one should trigger the block
        result = track_suspicious_activity("5.5.5.5", "failed_login")
        assert result is True

        record = SuspiciousActivity.objects.get(
            ip_address="5.5.5.5", activity_type="failed_login",
        )
        assert record.is_blocked is True
        assert record.blocked_until is not None

    def test_block_duration(self):
        threshold = ACTIVITY_THRESHOLDS["failed_login"]
        for _ in range(threshold):
            track_suspicious_activity("6.6.6.6", "failed_login")

        record = SuspiciousActivity.objects.get(
            ip_address="6.6.6.6", activity_type="failed_login", is_blocked=True,
        )
        # blocked_until should be ~BLOCK_DURATION from now
        expected_min = timezone.now() + BLOCK_DURATION - timedelta(seconds=5)
        expected_max = timezone.now() + BLOCK_DURATION + timedelta(seconds=5)
        assert expected_min <= record.blocked_until <= expected_max

    def test_different_types_tracked_separately(self):
        track_suspicious_activity("7.7.7.7", "failed_login")
        track_suspicious_activity("7.7.7.7", "rate_limit_exceeded")

        assert SuspiciousActivity.objects.filter(ip_address="7.7.7.7").count() == 2
        fl = SuspiciousActivity.objects.get(
            ip_address="7.7.7.7", activity_type="failed_login",
        )
        rl = SuspiciousActivity.objects.get(
            ip_address="7.7.7.7", activity_type="rate_limit_exceeded",
        )
        assert fl.count == 1
        assert rl.count == 1

    def test_different_ips_tracked_separately(self):
        track_suspicious_activity("8.8.8.8", "failed_login")
        track_suspicious_activity("9.9.9.9", "failed_login")

        assert SuspiciousActivity.objects.filter(activity_type="failed_login").count() == 2

    def test_with_account(self, account):
        track_suspicious_activity("10.0.0.1", "failed_login", account=account)
        record = SuspiciousActivity.objects.get(ip_address="10.0.0.1")
        assert record.account == account

    def test_rate_limit_threshold(self):
        threshold = ACTIVITY_THRESHOLDS["rate_limit_exceeded"]  # 10
        for _ in range(threshold):
            track_suspicious_activity("11.11.11.11", "rate_limit_exceeded")

        record = SuspiciousActivity.objects.get(
            ip_address="11.11.11.11", activity_type="rate_limit_exceeded",
        )
        assert record.is_blocked is True

    def test_unauthorized_access_threshold(self):
        threshold = ACTIVITY_THRESHOLDS["unauthorized_access"]  # 8
        for _ in range(threshold):
            track_suspicious_activity("12.12.12.12", "unauthorized_access")

        record = SuspiciousActivity.objects.get(
            ip_address="12.12.12.12", activity_type="unauthorized_access",
        )
        assert record.is_blocked is True


# ==============================================================================
# DETECTION SERVICE — is_blocked()
# ==============================================================================


@pytest.mark.django_db
class TestIsBlocked:
    """Test the blocking check function."""

    def test_unblocked_ip_returns_false(self):
        assert is_blocked("1.1.1.1") is False

    def test_blocked_ip_returns_true(self):
        SuspiciousActivity.objects.create(
            ip_address="2.2.2.2",
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        assert is_blocked("2.2.2.2") is True

    def test_expired_block_returns_false(self):
        SuspiciousActivity.objects.create(
            ip_address="3.3.3.3",
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() - timedelta(minutes=1),
        )
        assert is_blocked("3.3.3.3") is False

    def test_expired_block_auto_cleared(self):
        record = SuspiciousActivity.objects.create(
            ip_address="4.4.4.4",
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() - timedelta(minutes=1),
        )
        is_blocked("4.4.4.4")
        record.refresh_from_db()
        assert record.is_blocked is False

    def test_blocked_account_returns_true(self, account):
        SuspiciousActivity.objects.create(
            ip_address="5.5.5.5",
            activity_type="failed_login",
            account=account,
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        # Different IP but same account
        assert is_blocked("99.99.99.99", account=account) is True

    def test_unblocked_account_returns_false(self, account):
        assert is_blocked("99.99.99.99", account=account) is False


# ==============================================================================
# DETECTION SERVICE — reset_blocks()
# ==============================================================================


@pytest.mark.django_db
class TestResetBlocks:
    """Test manual block clearing."""

    def test_reset_by_ip(self):
        SuspiciousActivity.objects.create(
            ip_address="20.20.20.20",
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        count = reset_blocks(ip_address="20.20.20.20")
        assert count == 1
        assert is_blocked("20.20.20.20") is False

    def test_reset_by_account(self, account):
        SuspiciousActivity.objects.create(
            ip_address="21.21.21.21",
            activity_type="unauthorized_access",
            account=account,
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        count = reset_blocks(account=account)
        assert count == 1

    def test_reset_clears_multiple(self):
        for atype in ["failed_login", "rate_limit_exceeded"]:
            SuspiciousActivity.objects.create(
                ip_address="22.22.22.22",
                activity_type=atype,
                is_blocked=True,
                blocked_until=timezone.now() + timedelta(minutes=10),
            )
        count = reset_blocks(ip_address="22.22.22.22")
        assert count == 2

    def test_reset_no_match_returns_zero(self):
        count = reset_blocks(ip_address="255.255.255.255")
        assert count == 0


# ==============================================================================
# DETECTION SERVICE — get_block_status()
# ==============================================================================


@pytest.mark.django_db
class TestGetBlockStatus:
    """Test status summary function."""

    def test_no_blocks(self):
        result = get_block_status("1.1.1.1")
        assert result["is_blocked"] is False
        assert result["active_blocks"] == []

    def test_with_active_block(self):
        SuspiciousActivity.objects.create(
            ip_address="30.30.30.30",
            activity_type="failed_login",
            count=5,
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        result = get_block_status("30.30.30.30")
        assert result["is_blocked"] is True
        assert len(result["active_blocks"]) == 1
        assert result["active_blocks"][0]["activity_type"] == "failed_login"
        assert result["active_blocks"][0]["count"] == 5


# ==============================================================================
# BLOCKED USER MIDDLEWARE
# ==============================================================================


@pytest.mark.django_db
class TestBlockedUserMiddleware:
    """Test that BlockedUserMiddleware rejects blocked IPs."""

    def test_unblocked_request_passes_through(self):
        client = APIClient()
        # This will get a 401 (unauthenticated), not 403 (blocked)
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_blocked_ip_returns_403(self, account):
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",  # test client uses 127.0.0.1
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        client = APIClient()
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "blocked"

    def test_blocked_ip_response_message(self):
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",
            activity_type="rate_limit_exceeded",
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        client = APIClient()
        response = client.get("/api/v1/branches/branches/")
        data = response.json()
        assert data["success"] is False
        assert "suspicious activity" in data["error"]["message"]

    def test_expired_block_allows_through(self):
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",
            activity_type="failed_login",
            is_blocked=True,
            blocked_until=timezone.now() - timedelta(minutes=1),  # expired
        )
        client = APIClient()
        # Should pass through (get 401 for unauth, not 403 for blocked)
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_blocked_authenticated_user(self, account):
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",
            activity_type="unauthorized_access",
            account=account,
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=10),
        )
        client = APIClient()
        client.force_authenticate(user=account)
        response = client.get("/api/v1/branches/branches/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "blocked"

    def test_middleware_survives_detection_error(self):
        """If detection service crashes, request proceeds normally."""
        client = APIClient()
        with patch(
            "config.security.detection.is_blocked",
            side_effect=Exception("DB down"),
        ):
            # Middleware should catch the exception and let request through
            response = client.get("/api/v1/auth/accounts/")
            # Will get 401 (normal unauthenticated), not 500
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# MIDDLEWARE INTEGRATION — SecurityLoggingMiddleware feeds detection
# ==============================================================================


@pytest.mark.django_db
class TestLoggingMiddlewareDetectionIntegration:
    """Verify SecurityLoggingMiddleware feeds events into detection."""

    def test_401_feeds_failed_login(self):
        """A 401 response triggers track_suspicious_activity(failed_login)."""
        client = APIClient()
        client.get("/api/v1/auth/accounts/")

        # The middleware calls track_suspicious_activity internally.
        # Verify via the SuspiciousActivity table.
        assert SuspiciousActivity.objects.filter(
            activity_type="failed_login",
        ).exists()

    def test_403_feeds_unauthorized_access(self, api_client, client_profile):
        """A 403 response triggers track_suspicious_activity(unauthorized_access)."""
        api_client.force_authenticate(user=client_profile.account)
        api_client.post("/api/v1/bookings/bookings/", {})

        assert SuspiciousActivity.objects.filter(
            activity_type="unauthorized_access",
        ).exists()

    def test_detection_error_does_not_crash_request(self):
        """If detection service raises, the response still comes through."""
        client = APIClient()
        with patch(
            "config.security.detection.track_suspicious_activity",
            side_effect=Exception("DB error"),
        ):
            response = client.get("/api/v1/auth/accounts/")
            # Should still return 401, not 500
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# END-TO-END: Repeated failures → auto-block → auto-unblock
# ==============================================================================


@pytest.mark.django_db
class TestEndToEndBlockFlow:
    """Full cycle: repeated bad requests → block → recovery."""

    def test_repeated_401s_cause_block(self):
        """After ACTIVITY_THRESHOLDS['failed_login'] unauthenticated requests,
        the IP gets blocked."""
        client = APIClient()
        threshold = ACTIVITY_THRESHOLDS["failed_login"]  # 5

        # Fire off enough 401s to trigger the block.
        for _ in range(threshold):
            client.get("/api/v1/auth/accounts/")

        # Next request should be blocked (403 with "blocked" code).
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "blocked"

    def test_auto_unblock_after_duration(self):
        """Once blocked_until passes, the IP is auto-unblocked."""
        # Manually create an expired block
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",
            activity_type="failed_login",
            count=5,
            is_blocked=True,
            blocked_until=timezone.now() - timedelta(seconds=1),
        )
        client = APIClient()
        # Request should go through (get 401, not 403)
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_manual_reset_unblocks(self):
        """Admin can reset blocks and allow traffic again."""
        # Create active block
        SuspiciousActivity.objects.create(
            ip_address="127.0.0.1",
            activity_type="failed_login",
            count=10,
            is_blocked=True,
            blocked_until=timezone.now() + timedelta(minutes=15),
        )
        # Confirm blocked
        client = APIClient()
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Manual reset
        count = reset_blocks(ip_address="127.0.0.1")
        assert count == 1

        # Now unblocked
        response = client.get("/api/v1/auth/accounts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# CONFIGURATION TESTS
# ==============================================================================


class TestSuspiciousActivityConfiguration:
    """Verify configuration and middleware registration."""

    def test_blocked_user_middleware_in_settings(self):
        from django.conf import settings

        assert (
            "config.security.middleware.BlockedUserMiddleware"
            in settings.MIDDLEWARE
        )

    def test_blocked_middleware_after_auth_middleware(self):
        from django.conf import settings

        mw = settings.MIDDLEWARE
        auth_idx = mw.index(
            "django.contrib.auth.middleware.AuthenticationMiddleware",
        )
        blocked_idx = mw.index(
            "config.security.middleware.BlockedUserMiddleware",
        )
        assert blocked_idx > auth_idx

    def test_thresholds_defined(self):
        assert "failed_login" in ACTIVITY_THRESHOLDS
        assert "rate_limit_exceeded" in ACTIVITY_THRESHOLDS
        assert "unauthorized_access" in ACTIVITY_THRESHOLDS
        assert "abnormal_behavior" in ACTIVITY_THRESHOLDS

    def test_block_duration_is_15_minutes(self):
        assert BLOCK_DURATION == timedelta(minutes=15)

    def test_tracking_window_is_5_minutes(self):
        assert TRACKING_WINDOW == timedelta(minutes=5)
