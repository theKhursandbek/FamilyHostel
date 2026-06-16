"""
Mini App phone OTP endpoints (TELEGRAM_MINI_APP_PLAN.md §3.1, §4.1).

POST /api/v1/auth/telegram/phone/start    {phone}            → 202
POST /api/v1/auth/telegram/phone/verify   {phone, code}      → {verified, account_id}

Flow:
    1. Telegram bot or Mini App calls /start with phone (after the user
       shared their contact in the bot or typed it manually).
    2. Backend issues a 6-digit OTP, hashes it, stores ``OtpToken``
       (TTL 5 min, max 5 active per phone), and dispatches the SMS via
       ``apps.common.sms.send_sms``.
    3. Client posts the code to /verify; on success we mark the matching
       Account.client_profile.phone_verified=True and copy phone onto Account.

Rate limits (DRF scoped throttle):
    - ``otp_start``  : 5/hour anon
    - ``otp_verify`` : 10/hour anon

The actual JWT issuance still happens in :class:`TelegramAuthView`; this
module only opens the door by setting ``phone_verified``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.sms import SmsDeliveryError, send_sms
from apps.common.validators import validate_otp, validate_phone

from .models import Account, Client, OtpToken

logger = logging.getLogger("security")


OTP_TTL_SECONDS = getattr(settings, "OTP_TTL_SECONDS", 300)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
OTP_MAX_ACTIVE_PER_PHONE = getattr(settings, "OTP_MAX_ACTIVE_PER_PHONE", 5)
OTP_LENGTH = getattr(settings, "OTP_LENGTH", 6)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ---------------------------------------------------------------------------
# /auth/telegram/phone/start
# ---------------------------------------------------------------------------

class _StartInput(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        return validate_phone(value)


class PhoneOtpStartView(APIView):
    """Issue an OTP and dispatch via SMS. Idempotent re-tries are throttled."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_start"

    def post(self, request):
        serializer = _StartInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        now = timezone.now()
        active = OtpToken.objects.filter(
            phone=phone,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        if active.count() >= OTP_MAX_ACTIVE_PER_PHONE:
            logger.warning("OTP_FLOOD | phone=%s | ip=%s", phone, _client_ip(request))
            return Response(
                {"detail": "Too many active codes. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
        token = OtpToken.objects.create(
            phone=phone,
            code_hash=_hash_code(code),
            purpose=OtpToken.PURPOSE_ONBOARDING,
            expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
            ip_address=_client_ip(request) or None,
        )

        message = (
            f"Hotel: your verification code is {code}. "
            f"Valid for {OTP_TTL_SECONDS // 60} minutes."
        )
        try:
            send_sms(phone, message)
        except SmsDeliveryError as exc:
            logger.error("OTP_SMS_FAIL | phone=%s | %s", phone, exc)
            # Roll back the token so the count doesn't grow on transient failures.
            token.delete()
            return Response(
                {"detail": "SMS provider unavailable. Try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info("OTP_SENT | phone=%s | ttl=%s", phone, OTP_TTL_SECONDS)
        return Response(
            {"sent": True, "expires_in": OTP_TTL_SECONDS},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# /auth/telegram/phone/verify
# ---------------------------------------------------------------------------

class _VerifyInput(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()

    def validate_phone(self, value):
        return validate_phone(value)

    def validate_code(self, value):
        return validate_otp(value)


class PhoneOtpVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    @transaction.atomic
    def post(self, request):
        serializer = _VerifyInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]
        code_hash = _hash_code(code)
        now = timezone.now()

        token = (
            OtpToken.objects
            .select_for_update()
            .filter(
                phone=phone,
                consumed_at__isnull=True,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
        if token is None:
            return Response(
                {"detail": "No active code. Request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token.attempts >= OTP_MAX_ATTEMPTS:
            return Response(
                {"detail": "Too many wrong attempts. Request a new code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not secrets.compare_digest(token.code_hash, code_hash):
            token.attempts += 1
            token.save(update_fields=["attempts"])
            logger.warning(
                "OTP_BAD | phone=%s | attempts=%s", phone, token.attempts,
            )
            return Response(
                {"detail": "Incorrect code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token.consumed_at = now
        token.save(update_fields=["consumed_at"])

        # Flip phone_verified on any matching account/client.
        account = Account.objects.filter(phone=phone).first()
        client_id = None
        if account is not None:
            client = getattr(account, "client_profile", None)
            if client is not None:
                client.phone_verified = True
                client.save(update_fields=["phone_verified"])
                client_id = client.pk

        logger.info("OTP_OK | phone=%s | account=%s", phone, account.pk if account else None)
        return Response({
            "verified": True,
            "phone": phone,
            "account_id": account.pk if account else None,
            "client_id": client_id,
        })
