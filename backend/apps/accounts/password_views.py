"""
Password management endpoints for the Telegram Mini App.

    POST /api/v1/auth/password/change/
        Authenticated. Requires OTP code (sent via Telegram) + new password.

    POST /api/v1/auth/password/reset/
        Unauthenticated. Requires phone + OTP code + new password.
        On success returns a fresh JWT pair so the client is auto-logged-in.

Security notes:
    - OTP is 6 digits, SHA-256 hashed, consumed atomically (one-time).
    - Rate-limited via ``otp_verify`` throttle scope (10/hour per IP).
    - New password: min 8 chars, must contain both letters and digits.
    - Passwords never echoed back in responses.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Account, OtpToken
from .otp_utils import consume_otp

logger = logging.getLogger("security")

_PWD_MIN = 8
_PWD_MAX = 128


def _client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


def _validate_new_password(new_pw: str, confirm: str) -> str | None:
    """Return an error string, or None if the password is acceptable."""
    if not new_pw:
        return "New password is required."
    if len(new_pw) < _PWD_MIN:
        return f"Password must be at least {_PWD_MIN} characters."
    if len(new_pw) > _PWD_MAX:
        return "Password is too long."
    if any(c in new_pw for c in (" ", "\t", "\n")):
        return "Password must not contain spaces."
    has_letter = any(c.isalpha() for c in new_pw)
    has_digit = any(c.isdigit() for c in new_pw)
    if not has_letter or not has_digit:
        return "Password must contain both letters and digits."
    if new_pw != confirm:
        return "Passwords do not match."
    return None


def _validate_otp_format(code: str) -> bool:
    return bool(code) and len(code) == 6 and code.isdigit()


# ---------------------------------------------------------------------------
# Change password (authenticated)
# ---------------------------------------------------------------------------

class ChangePasswordView(APIView):
    """POST /auth/password/change/ — change own password using current password."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"  # same rate limit: 10/hour per IP

    def post(self, request):
        current_password = request.data.get("current_password", "")
        new_password = request.data.get("new_password", "")
        confirm = request.data.get("confirm_password", "")

        if not current_password:
            return Response(
                {"detail": "current_password_wrong", "code": "current_password_wrong"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Constant-time check via Django's PBKDF2/bcrypt verifier.
        if not request.user.check_password(current_password):
            logger.warning(
                "CHANGE_PWD_WRONG_CURRENT | account=%s | ip=%s",
                request.user.pk, _client_ip(request),
            )
            return Response(
                {"detail": "current_password_wrong", "code": "current_password_wrong"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        err = _validate_new_password(new_password, confirm)
        if err:
            return Response({"detail": err, "code": err}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save(update_fields=["password", "updated_at"])

        logger.info("CHANGE_PWD_OK | account=%s", request.user.pk)
        return Response({"changed": True})


# ---------------------------------------------------------------------------
# Reset (forgot) password (unauthenticated)
# ---------------------------------------------------------------------------

class ResetPasswordView(APIView):
    """POST /auth/password/reset/ — forgot-password reset (no auth required)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        from rest_framework import serializers as _ser
        from rest_framework_simplejwt.tokens import RefreshToken

        raw_phone = (request.data.get("phone") or "").strip()
        code = (request.data.get("code") or "").strip()
        new_password = request.data.get("new_password", "")
        confirm = request.data.get("confirm_password", "")

        # --- Validate phone ---
        try:
            from apps.common.validators import validate_phone as _vp
            phone = _vp(raw_phone)
        except _ser.ValidationError:
            return Response(
                {"detail": "Invalid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not _validate_otp_format(code):
            return Response(
                {"detail": "OTP must be exactly 6 digits."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        err = _validate_new_password(new_password, confirm)
        if err:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)

        # --- Verify OTP (atomic, not inside outer txn) ---
        ok, detail, http_status = consume_otp(phone, code, OtpToken.PURPOSE_FORGOT_PASSWORD)
        if not ok:
            logger.warning(
                "RESET_PWD_OTP_FAIL | phone=%s | ip=%s", phone, _client_ip(request),
            )
            return Response({"detail": detail}, status=http_status)

        # --- Set new password ---
        account = Account.objects.filter(phone=phone).first()
        if account is None:
            # Extremely unlikely (OTP token existed for this phone)
            return Response(
                {"detail": "Account not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.set_password(new_password)
        account.save(update_fields=["password", "updated_at"])

        logger.info("RESET_PWD_OK | account=%s", account.pk)

        # Issue fresh tokens so the client is auto-logged-in after reset.
        refresh = RefreshToken.for_user(account)
        return Response({
            "reset": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
