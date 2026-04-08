"""
Telegram Mini App authentication (Step 21).

Implements:
    - ``validate_telegram_init_data()``: validates Telegram WebApp initData.
    - ``TelegramAuthView``: ``POST /api/v1/auth/telegram/`` endpoint.

References:
    - README Section 17        (POST /auth/telegram/)
    - README Section 25.5      (JWT authentication)
    - README Section 26.5      (Security Configuration)
    - Telegram WebApp Docs:
      https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from config.api.exceptions import ServiceUnavailable

from .models import Account, Client

logger = logging.getLogger("security")

__all__ = ["TelegramAuthView", "validate_telegram_init_data"]


# ==============================================================================
# TELEGRAM INIT DATA VALIDATION
# ==============================================================================

_AUTH_DATE_MAX_AGE = 86_400  # 24 hours in seconds


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Validate Telegram Mini App ``initData``.

    Algorithm (per Telegram docs):
        1. Parse the query string.
        2. Extract and remove the ``hash`` parameter.
        3. Sort remaining params alphabetically.
        4. Build ``data_check_string`` as ``key=value\\n`` lines.
        5. HMAC-SHA256 validate using the bot token.

    Returns:
        Parsed user data dict if valid, ``None`` if invalid or expired.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)

    # Extract hash
    received_hash = parsed.pop("hash", [None])[0]
    if not received_hash:
        return None

    # Build data-check-string (sorted, URL-decoded values)
    data_check_parts = []
    for key in sorted(parsed.keys()):
        data_check_parts.append(f"{key}={parsed[key][0]}")
    data_check_string = "\n".join(data_check_parts)

    # HMAC verification
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    # Check auth_date freshness
    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        try:
            if time.time() - int(auth_date_str) > _AUTH_DATE_MAX_AGE:
                return None
        except (ValueError, TypeError):
            return None

    # Parse user JSON
    user_raw = parsed.get("user", [None])[0]
    if user_raw:
        try:
            return json.loads(user_raw)
        except json.JSONDecodeError:
            return None

    return None


# ==============================================================================
# SERIALIZER
# ==============================================================================


class TelegramAuthSerializer(serializers.Serializer):
    """Input serializer for Telegram authentication."""

    init_data = serializers.CharField(
        help_text="Telegram Mini App initData query string.",
    )


# ==============================================================================
# VIEW
# ==============================================================================


class TelegramAuthView(APIView):
    """
    ``POST /api/v1/auth/telegram/``

    Authenticate a user via Telegram Mini App ``initData``.
    Validates the data, creates or retrieves the account, and returns
    JWT access + refresh tokens.

    Request body::

        {"init_data": "<Telegram WebApp initData string>"}

    Success response::

        {
            "account_id": 1,
            "telegram_id": 123456789,
            "roles": ["client"],
            "is_new": true,
            "access": "<JWT access token>",
            "refresh": "<JWT refresh token>"
        }
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth required for login
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = TelegramAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        init_data: str = serializer.validated_data["init_data"]  # type: ignore[index]
        bot_token = settings.TELEGRAM_BOT_TOKEN

        if not bot_token:
            raise ServiceUnavailable("Telegram bot is not configured.")

        user_data = validate_telegram_init_data(init_data, bot_token)
        if user_data is None:
            logger.warning(
                "TELEGRAM_AUTH_FAILED | ip=%s | Invalid initData",
                self._get_client_ip(request),
            )
            # Return plain 401 instead of raising AuthenticationFailed,
            # because authentication_classes=[] causes DRF to convert 401→403.
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "authentication_failed",
                        "message": "Invalid Telegram authentication data.",
                    },
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        telegram_id = user_data.get("id")
        if not telegram_id:
            raise ValidationError(
                {"detail": "Telegram user ID not found in auth data."},
            )

        # Get or create account
        account, created = Account.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={"is_active": True},
        )

        if not account.is_active:
            raise PermissionDenied("Account is deactivated.")

        # Create client profile for new accounts (README Section 3.5)
        if created:
            first_name = user_data.get("first_name", "")
            last_name = user_data.get("last_name", "")
            full_name = (
                f"{first_name} {last_name}".strip() or f"User {telegram_id}"
            )
            Client.objects.create(account=account, full_name=full_name)

        # Generate JWT tokens (README Section 25.5)
        refresh = RefreshToken.for_user(account)

        logger.info(
            "TELEGRAM_AUTH_OK | telegram_id=%s | new=%s",
            telegram_id,
            created,
        )

        return Response({
            "account_id": account.pk,
            "telegram_id": account.telegram_id,
            "roles": account.roles,
            "is_new": created,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })

    @staticmethod
    def _get_client_ip(request) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
