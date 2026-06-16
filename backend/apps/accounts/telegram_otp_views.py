"""
Telegram-bot OTP dispatch endpoint.

    POST /api/v1/auth/otp/telegram/send/

Body fields:
    purpose  — "register" | "change_password" | "forgot_password"
    phone    — required for "register" and "forgot_password"; ignored for
               "change_password" (account's own phone is used)

For ``register`` and ``change_password`` the caller must carry a valid JWT.
For ``forgot_password`` no authentication is required.

The OTP is sent to ``account.telegram_chat_id`` via the Telegram bot using
the ``send_telegram_message_task`` Celery task (apps.reports.tasks).

Rate limit: ``otp_start`` — 5 requests / hour per IP (configured in settings).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Account, OtpToken

logger = logging.getLogger("security")

OTP_TTL_SECONDS: int = getattr(settings, "OTP_TTL_SECONDS", 300)
OTP_MAX_ACTIVE_PER_PHONE: int = getattr(settings, "OTP_MAX_ACTIVE_PER_PHONE", 5)
OTP_LENGTH: int = getattr(settings, "OTP_LENGTH", 6)

_VALID_PURPOSES = (
    OtpToken.PURPOSE_REGISTER,
    OtpToken.PURPOSE_CHANGE_PASSWORD,
    OtpToken.PURPOSE_FORGOT_PASSWORD,
)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


def _send_via_telegram(chat_id: str, code: str, purpose: str, lang: str = "ru") -> None:
    """Send OTP via the hostel Telegram bot using the Celery task."""
    from apps.reports.tasks import send_telegram_message_task  # lazy to avoid app-registry issues

    ttl_min = OTP_TTL_SECONDS // 60
    templates = {
        OtpToken.PURPOSE_REGISTER: {
            "uz": (
                f"🔐 <b>Hotel</b> ro'yxatdan o'tish kodi:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ {ttl_min} daqiqa amal qiladi.\n"
                f"Bu kodni hech kimga bermang."
            ),
            "ru": (
                f"🔐 Код подтверждения <b>Hotel</b>:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Действителен {ttl_min} минут.\n"
                f"Никому не сообщайте этот код."
            ),
            "en": (
                f"🔐 <b>Hotel</b> registration code:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Valid for {ttl_min} minutes.\n"
                f"Never share this code with anyone."
            ),
        },
        OtpToken.PURPOSE_CHANGE_PASSWORD: {
            "uz": (
                f"🔑 Parolni o'zgartirish kodi:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ {ttl_min} daqiqa amal qiladi.\n"
                f"Agar siz so'ramagan bo'lsangiz — hisobingizni himoya qiling."
            ),
            "ru": (
                f"🔑 Код смены пароля:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Действителен {ttl_min} минут.\n"
                f"Если вы не запрашивали — защитите аккаунт немедленно."
            ),
            "en": (
                f"🔑 Password change code:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Valid for {ttl_min} minutes.\n"
                f"If you didn't request this — secure your account immediately."
            ),
        },
        OtpToken.PURPOSE_FORGOT_PASSWORD: {
            "uz": (
                f"🔑 Parolni tiklash kodi:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ {ttl_min} daqiqa amal qiladi.\n"
                f"Bu kodni hech kimga bermang."
            ),
            "ru": (
                f"🔑 Код восстановления пароля:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Действителен {ttl_min} минут.\n"
                f"Никому не сообщайте этот код."
            ),
            "en": (
                f"🔑 Password reset code:\n\n"
                f"<b>{code}</b>\n\n"
                f"⏱ Valid for {ttl_min} minutes.\n"
                f"Never share this code with anyone."
            ),
        },
    }

    lang_key = lang if lang in ("uz", "ru", "en") else "ru"
    purpose_msgs = templates.get(purpose, templates[OtpToken.PURPOSE_REGISTER])
    msg = purpose_msgs.get(lang_key, purpose_msgs["ru"])

    send_telegram_message_task.delay(chat_id, msg, "HTML")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class TelegramOtpSendView(APIView):
    """POST /auth/otp/telegram/send/ — issue OTP and dispatch via Telegram bot."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_start"

    def post(self, request):
        from rest_framework import serializers as _ser

        purpose = (request.data.get("purpose") or "").strip()
        if purpose not in _VALID_PURPOSES:
            return Response(
                {"detail": "Invalid purpose.", "code": "invalid_purpose"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # Resolve account + phone
        # ------------------------------------------------------------------
        if purpose == OtpToken.PURPOSE_CHANGE_PASSWORD:
            # Auth required only for change_password
            if not (request.user and request.user.is_authenticated):
                return Response(
                    {"detail": "Authentication required.", "code": "auth_required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            account: Account = request.user
            phone = account.phone or ""
            if not phone:
                return Response(
                    {"detail": "No phone number on your account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if purpose == OtpToken.PURPOSE_REGISTER:
            # No auth required — user is not yet registered
            raw_phone = (request.data.get("phone") or "").strip()
            try:
                from apps.common.validators import validate_phone as _vp
                phone = _vp(raw_phone)
            except _ser.ValidationError:
                return Response(
                        {"detail": "Invalid phone number."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Look up the account by phone so we can get telegram_chat_id.
            # If not found or no Telegram linked, return no_telegram so the
            # frontend gracefully falls back to direct registration.
            account = Account.objects.filter(phone=phone).first()
            if account is None or not getattr(account, "telegram_chat_id", None):
                return Response(
                    {
                        "detail": "Telegram not linked. Registering without OTP.",
                        "code": "no_telegram",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        else:  # PURPOSE_FORGOT_PASSWORD — no auth needed
            raw_phone = (request.data.get("phone") or "").strip()
            try:
                from apps.common.validators import validate_phone as _vp
                phone = _vp(raw_phone)
            except _ser.ValidationError:
                return Response(
                    {"detail": "Invalid phone number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            account = Account.objects.filter(phone=phone).first()
            if account is None:
                # Security: do NOT reveal whether this phone is registered.
                logger.info(
                    "TELEGRAM_OTP_FORGOT_NO_ACCOUNT | phone=%s | ip=%s",
                    phone, _client_ip(request),
                )
                return Response(
                    {"sent": True, "expires_in": OTP_TTL_SECONDS},
                    status=status.HTTP_202_ACCEPTED,
                )

        # ------------------------------------------------------------------
        # Verify Telegram is linked
        # ------------------------------------------------------------------
        chat_id = getattr(account, "telegram_chat_id", None)
        if not chat_id:
            return Response(
                {
                    "detail": "Telegram not linked. Open this app from Telegram.",
                    "code": "no_telegram",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------
        # Rate-limit: cap active tokens per phone+purpose
        # ------------------------------------------------------------------
        now = timezone.now()
        active_count = OtpToken.objects.filter(
            phone=phone,
            purpose=purpose,
            consumed_at__isnull=True,
            expires_at__gt=now,
        ).count()
        if active_count >= OTP_MAX_ACTIVE_PER_PHONE:
            logger.warning(
                "TELEGRAM_OTP_FLOOD | phone=%s | purpose=%s | ip=%s",
                phone, purpose, _client_ip(request),
            )
            return Response(
                {"detail": "Too many active codes. Please wait a few minutes and try again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ------------------------------------------------------------------
        # Issue token + send
        # ------------------------------------------------------------------
        code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
        OtpToken.objects.create(
            phone=phone,
            code_hash=_hash_code(code),
            purpose=purpose,
            expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
            ip_address=_client_ip(request) or None,
        )

        lang = getattr(account, "language", "ru") or "ru"
        _send_via_telegram(chat_id, code, purpose, lang)

        logger.info(
            "TELEGRAM_OTP_SENT | phone=%s | purpose=%s | chat_id=%s",
            phone, purpose, chat_id,
        )
        return Response(
            {"sent": True, "expires_in": OTP_TTL_SECONDS},
            status=status.HTTP_202_ACCEPTED,
        )
