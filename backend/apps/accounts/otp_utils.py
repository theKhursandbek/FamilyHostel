"""
Shared OTP verification helper.

Imported by otp_views, telegram_otp_views, password_views, and client_auth
to keep the consume logic in one place and avoid duplication.

``consume_otp`` performs a SELECT FOR UPDATE inside its own savepoint-free
transaction so that:
  - failed attempts are always persisted (even if the caller rolls back),
  - the consumed token is durable once the function returns True.

This means callers must NOT wrap consume_otp inside their own transaction
that they might roll back after the OTP check passes.
"""

from __future__ import annotations

import hashlib
import logging
import secrets

from django.db import transaction
from django.utils import timezone
from rest_framework import status

logger = logging.getLogger("security")

OTP_MAX_ATTEMPTS: int = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def consume_otp(phone: str, code: str, purpose: str) -> tuple[bool, str | None, int]:
    """Atomically verify and consume an OTP token.

    Returns ``(success, error_detail, http_status_code)``.
    On success: ``error_detail`` is ``None``, ``http_status_code`` is 200.
    On failure: ``success`` is ``False``, ``error_detail`` is a human-readable
    string safe to return to the client, ``http_status_code`` is 400 or 429.

    The inner ``transaction.atomic`` block is deliberately NOT marked as a
    savepoint so that the attempts increment is committed immediately, preventing
    a brute-force attack from repeatedly resetting the counter by wrapping the
    call in an outer transaction that rolls back.
    """
    from .models import OtpToken  # lazy import — avoids circular at module level

    code_hash = _hash_code(code)
    now = timezone.now()

    with transaction.atomic():
        token = (
            OtpToken.objects
            .select_for_update()
            .filter(
                phone=phone,
                consumed_at__isnull=True,
                expires_at__gt=now,
                purpose=purpose,
            )
            .order_by("-created_at")
            .first()
        )

        if token is None:
            return False, "otp_expired", status.HTTP_400_BAD_REQUEST

        if token.attempts >= OTP_MAX_ATTEMPTS:
            return (
                False,
                "otp_max_attempts",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not secrets.compare_digest(token.code_hash, code_hash):
            token.attempts += 1
            token.save(update_fields=["attempts"])
            remaining = OTP_MAX_ATTEMPTS - token.attempts
            logger.warning(
                "OTP_BAD | phone=%s | purpose=%s | attempts=%s",
                phone, purpose, token.attempts,
            )
            if remaining > 0:
                return False, "otp_invalid", status.HTTP_400_BAD_REQUEST
            else:
                return False, "otp_max_attempts", status.HTTP_400_BAD_REQUEST

        token.consumed_at = now
        token.save(update_fields=["consumed_at"])
        logger.info("OTP_CONSUMED | phone=%s | purpose=%s", phone, purpose)
        return True, None, status.HTTP_200_OK
