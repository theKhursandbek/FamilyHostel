"""
Tests for Step 21 — Security hardening for production.

Covers:
    - Telegram Mini App authentication (validate initData → JWT tokens)
    - JWT access / refresh token flow
    - Permissions enforcement across ViewSets
    - Security configuration verification
    - Security headers middleware
    - Security logging middleware
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.authentication import validate_telegram_init_data
from conftest import AccountFactory, ClientFactory

# ==============================================================================
# HELPERS
# ==============================================================================

BOT_TOKEN = "test_bot_token_12345"


def _generate_init_data(
    bot_token: str,
    user_data: dict,
    auth_date: int | None = None,
) -> str:
    """Generate valid Telegram Mini App initData for testing."""
    if auth_date is None:
        auth_date = int(time.time())

    user_json = json.dumps(user_data, separators=(",", ":"))
    params = {"user": user_json, "auth_date": str(auth_date)}

    # Build data-check-string from sorted params
    data_check_parts = [f"{k}={params[k]}" for k in sorted(params)]
    data_check_string = "\n".join(data_check_parts)

    # Calculate HMAC
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256,
    ).digest()
    hash_val = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256,
    ).hexdigest()

    params["hash"] = hash_val
    return urlencode(params)


# ==============================================================================
# UNIT TESTS — validate_telegram_init_data()
# ==============================================================================


class TestValidateTelegramInitData:
    """Unit tests for the initData validation function."""

    def test_valid_data_returns_user_dict(self):
        user = {"id": 123, "first_name": "Alice"}
        init_data = _generate_init_data(BOT_TOKEN, user)
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is not None
        assert result["id"] == 123
        assert result["first_name"] == "Alice"

    def test_invalid_hash_returns_none(self):
        init_data = "user=%7B%22id%22%3A123%7D&auth_date=9999999999&hash=badhash"
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_missing_hash_returns_none(self):
        init_data = "user=%7B%22id%22%3A123%7D&auth_date=9999999999"
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_expired_auth_date_returns_none(self):
        user = {"id": 123, "first_name": "Old"}
        expired = int(time.time()) - 90_000  # >24 hours ago
        init_data = _generate_init_data(BOT_TOKEN, user, auth_date=expired)
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_no_user_field_returns_none(self):
        """initData without a 'user' param returns None."""
        auth_date = str(int(time.time()))
        params = {"auth_date": auth_date}

        data_check_parts = [f"{k}={params[k]}" for k in sorted(params)]
        data_check_string = "\n".join(data_check_parts)
        secret = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256,
        ).digest()
        hash_val = hmac.new(
            secret, data_check_string.encode(), hashlib.sha256,
        ).hexdigest()

        params["hash"] = hash_val
        init_data = urlencode(params)
        result = validate_telegram_init_data(init_data, BOT_TOKEN)
        assert result is None

    def test_wrong_bot_token_returns_none(self):
        user = {"id": 123, "first_name": "Alice"}
        init_data = _generate_init_data(BOT_TOKEN, user)
        result = validate_telegram_init_data(init_data, "wrong_token")
        assert result is None


# ==============================================================================
# INTEGRATION TESTS — Telegram Auth Endpoint
# ==============================================================================


@pytest.mark.django_db
class TestTelegramAuthEndpoint:
    """POST /api/v1/auth/telegram/"""

    url = "/api/v1/auth/telegram/"

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_valid_auth_creates_account_and_client(self):
        client = APIClient()
        user_data = {"id": 999888777, "first_name": "Test", "last_name": "User"}
        init_data = _generate_init_data(BOT_TOKEN, user_data)

        response: Response = client.post(self.url, {"init_data": init_data})  # type: ignore[assignment]

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data is not None
        assert data["telegram_id"] == 999888777
        assert data["is_new"] is True
        assert "access" in data
        assert "refresh" in data
        assert "client" in data["roles"]

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_valid_auth_existing_account(self):
        account = AccountFactory(telegram_id=999888777)
        ClientFactory(account=account, full_name="Existing User")

        client = APIClient()
        user_data = {"id": 999888777, "first_name": "Test"}
        init_data = _generate_init_data(BOT_TOKEN, user_data)

        response: Response = client.post(self.url, {"init_data": init_data})  # type: ignore[assignment]

        assert response.status_code == status.HTTP_200_OK
        assert response.data is not None
        assert response.data["is_new"] is False
        assert response.data["account_id"] == account.pk

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_invalid_hash_rejected(self):
        client = APIClient()
        init_data = (
            "user=%7B%22id%22%3A123%7D&auth_date=9999999999&hash=invalidhash"
        )

        response: Response = client.post(self.url, {"init_data": init_data})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_expired_auth_date_rejected(self):
        client = APIClient()
        user_data = {"id": 999888777, "first_name": "Expired"}
        expired_time = int(time.time()) - 90_000  # >24 hours
        init_data = _generate_init_data(BOT_TOKEN, user_data, auth_date=expired_time)

        response: Response = client.post(self.url, {"init_data": init_data})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_missing_init_data_returns_400(self):
        client = APIClient()
        response: Response = client.post(self.url, {})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_bot_not_configured_returns_503(self):
        client = APIClient()
        response: Response = client.post(self.url, {"init_data": "fake_data"})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_deactivated_account_returns_403(self):
        AccountFactory(telegram_id=111222333, is_active=False)

        client = APIClient()
        user_data = {"id": 111222333, "first_name": "Blocked"}
        init_data = _generate_init_data(BOT_TOKEN, user_data)

        response: Response = client.post(self.url, {"init_data": init_data})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# INTEGRATION TESTS — JWT Token Flow
# ==============================================================================


@pytest.mark.django_db
class TestJWTTokenFlow:
    """Test that JWT tokens work end-to-end."""

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_access_token_grants_api_access(self):
        """Bearer token allows access to protected endpoints."""
        client = APIClient()
        user_data = {"id": 555666777, "first_name": "JWT", "last_name": "Tester"}
        init_data = _generate_init_data(BOT_TOKEN, user_data)

        # Authenticate
        auth_resp: Response = client.post("/api/v1/auth/telegram/", {"init_data": init_data})  # type: ignore[assignment]
        assert auth_resp.data is not None
        access_token = auth_resp.data["access"]

        # Access protected endpoint (branches list — ReadOnly for any role)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response: Response = client.get("/api/v1/branches/branches/")  # type: ignore[assignment]
        assert response.status_code == status.HTTP_200_OK

    @override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
    def test_refresh_token_provides_new_access(self):
        """POST /auth/token/refresh/ returns a new access token."""
        client = APIClient()
        user_data = {"id": 555666778, "first_name": "Refresh"}
        init_data = _generate_init_data(BOT_TOKEN, user_data)

        auth_resp: Response = client.post("/api/v1/auth/telegram/", {"init_data": init_data})  # type: ignore[assignment]
        assert auth_resp.data is not None
        refresh_token = auth_resp.data["refresh"]

        # Refresh
        refresh_resp: Response = client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": refresh_token},
        )  # type: ignore[assignment]
        assert refresh_resp.status_code == status.HTTP_200_OK
        assert refresh_resp.data is not None
        assert "access" in refresh_resp.data

    def test_invalid_jwt_returns_401(self):
        """Invalid Bearer token is rejected."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        response: Response = client.get("/api/v1/branches/branches/")  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_credentials_returns_401(self):
        """Request without any credentials is rejected."""
        client = APIClient()
        response: Response = client.get("/api/v1/branches/branches/")  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# PERMISSIONS ENFORCEMENT
# ==============================================================================


@pytest.mark.django_db
class TestPermissionsEnforcement:
    """Verify role-based access per README Section 18 Permission Matrix."""

    def test_unauthenticated_blocked_from_accounts(self):
        client = APIClient()
        response: Response = client.get("/api/v1/auth/accounts/")  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_client_cannot_create_booking(self, api_client, client_profile, room, branch):
        """Clients cannot create bookings (Admin+ only)."""
        api_client.force_authenticate(user=client_profile.account)
        response: Response = api_client.post("/api/v1/bookings/bookings/", {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-06-01",
            "check_out_date": "2026-06-05",
            "price_at_booking": "500000",
        })  # type: ignore[assignment]
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_cannot_create_booking(self, staff_client):
        """Staff cannot create bookings (Admin+ only)."""
        response = staff_client.post("/api/v1/bookings/bookings/", {})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_list_bookings(self, admin_client):
        """Admin can read bookings."""
        response = admin_client.get("/api/v1/bookings/bookings/")
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_assign_shifts(self, staff_client):
        """Staff cannot create shift assignments (Director+ only)."""
        response = staff_client.post("/api/v1/staff/shifts/", {})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_director_can_list_shifts(self, director_client):
        """Director can read shift assignments."""
        response = director_client.get("/api/v1/staff/shifts/")
        assert response.status_code == status.HTTP_200_OK


# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================


class TestSecurityConfiguration:
    """Verify security settings are wired correctly."""

    def test_jwt_in_default_authentication_classes(self):
        from django.conf import settings

        auth_classes = settings.REST_FRAMEWORK.get(
            "DEFAULT_AUTHENTICATION_CLASSES", [],
        )
        assert any("JWTAuthentication" in cls for cls in auth_classes)

    def test_session_auth_still_available(self):
        from django.conf import settings

        auth_classes = settings.REST_FRAMEWORK.get(
            "DEFAULT_AUTHENTICATION_CLASSES", [],
        )
        assert any("SessionAuthentication" in cls for cls in auth_classes)

    def test_throttle_rates_defined(self):
        from django.conf import settings

        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        assert "anon" in rates
        assert "user" in rates
        assert "auth" in rates

    def test_simple_jwt_settings_exist(self):
        from django.conf import settings

        assert hasattr(settings, "SIMPLE_JWT")
        jwt_conf = settings.SIMPLE_JWT
        assert "ACCESS_TOKEN_LIFETIME" in jwt_conf
        assert "REFRESH_TOKEN_LIFETIME" in jwt_conf
        assert jwt_conf["AUTH_HEADER_TYPES"] == ("Bearer",)

    def test_security_middleware_present(self):
        from django.conf import settings

        assert (
            "config.security.middleware.SecurityLoggingMiddleware"
            in settings.MIDDLEWARE
        )
        assert (
            "config.security.middleware.SecurityHeadersMiddleware"
            in settings.MIDDLEWARE
        )


# ==============================================================================
# SECURITY HEADERS MIDDLEWARE
# ==============================================================================


@pytest.mark.django_db
class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware adds headers when configured."""

    @override_settings(
        CONTENT_SECURITY_POLICY="default-src 'self'",
        PERMISSIONS_POLICY="camera=()",
    )
    def test_csp_header_present(self):
        # Must re-init middleware with new settings → use fresh client
        from django.test import Client

        client = Client()
        response = client.get("/api/v1/branches/branches/")
        assert response.get("Content-Security-Policy") == "default-src 'self'"

    @override_settings(
        CONTENT_SECURITY_POLICY="default-src 'self'",
        PERMISSIONS_POLICY="camera=()",
    )
    def test_permissions_policy_header_present(self):
        from django.test import Client

        client = Client()
        response = client.get("/api/v1/branches/branches/")
        assert response.get("Permissions-Policy") == "camera=()"

    def test_no_headers_without_settings(self):
        """Without CONTENT_SECURITY_POLICY / PERMISSIONS_POLICY, no headers."""
        from django.test import Client

        client = Client()
        response = client.get("/api/v1/branches/branches/")
        # Default test settings do NOT set these, so headers absent
        assert response.get("Content-Security-Policy") is None
        assert response.get("Permissions-Policy") is None


# ==============================================================================
# SECURITY LOGGING MIDDLEWARE
# ==============================================================================


@pytest.mark.django_db
class TestSecurityLoggingMiddleware:
    """Test that security events are logged."""

    def test_401_logged_as_auth_failed(self):
        client = APIClient()
        with patch("config.security.middleware.logger") as mock_logger:
            client.get("/api/v1/auth/accounts/")
        mock_logger.warning.assert_called_once()
        log_fmt = mock_logger.warning.call_args[0][0]
        assert "AUTH_FAILED" in log_fmt

    def test_403_logged_as_permission_denied(self, api_client, client_profile):
        api_client.force_authenticate(user=client_profile.account)
        with patch("config.security.middleware.logger") as mock_logger:
            api_client.post("/api/v1/bookings/bookings/", {})
        mock_logger.warning.assert_called_once()
        log_fmt = mock_logger.warning.call_args[0][0]
        assert "PERMISSION_DENIED" in log_fmt
