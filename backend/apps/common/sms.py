"""
SMS dispatch backends for Mini App OTP flow.

Two backends:
    - ``EskizBackend``   — production; talks to https://notify.eskiz.uz/api.
    - ``MemorySmsBackend`` — tests/dev; appends to an in-process list.

Selected via ``settings.SMS_BACKEND`` (dotted path). All backends share the
same minimal interface::

    backend.send(phone: str, message: str) -> None

Failures raise :class:`SmsDeliveryError`; callers (OTP view) translate that
into a 503 response so the client can retry.
"""

from __future__ import annotations

import logging
import threading
from importlib import import_module
from typing import Optional

from django.conf import settings

logger = logging.getLogger("sms")


class SmsDeliveryError(Exception):
    """Raised when an SMS could not be dispatched."""


class BaseSmsBackend:
    def send(self, phone: str, message: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory backend (tests + offline dev)
# ---------------------------------------------------------------------------

class MemorySmsBackend(BaseSmsBackend):
    """Records every outgoing SMS in a class-level list. Thread-safe."""

    _lock = threading.Lock()
    outbox: list[dict] = []

    def send(self, phone: str, message: str) -> None:
        with self._lock:
            self.outbox.append({"phone": phone, "message": message})
        logger.info("SMS_MEMORY_SENT | phone=%s | len=%d", phone, len(message))

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls.outbox.clear()

    @classmethod
    def last_for(cls, phone: str) -> Optional[dict]:
        with cls._lock:
            for entry in reversed(cls.outbox):
                if entry["phone"] == phone:
                    return entry
        return None


# ---------------------------------------------------------------------------
# Eskiz.uz backend (production default for Uzbekistan)
# ---------------------------------------------------------------------------

class EskizBackend(BaseSmsBackend):
    """
    Eskiz.uz REST client.

    Auth model: long-lived email+password → bearer token. We cache the
    token in Django's default cache (key ``sms:eskiz:token``) for 25 days
    (Eskiz tokens last 30; we refresh proactively).

    Required settings:
        - ``ESKIZ_BASE_URL`` (default ``https://notify.eskiz.uz/api``)
        - ``ESKIZ_EMAIL``
        - ``ESKIZ_PASSWORD``
        - ``ESKIZ_FROM`` (sender id, default ``"4546"`` — Eskiz default test sender)
    """

    TOKEN_CACHE_KEY = "sms:eskiz:token"
    TOKEN_TTL = 60 * 60 * 24 * 25  # 25 days

    def __init__(self) -> None:
        self.base_url = getattr(
            settings, "ESKIZ_BASE_URL", "https://notify.eskiz.uz/api"
        ).rstrip("/")
        self.email = getattr(settings, "ESKIZ_EMAIL", "")
        self.password = getattr(settings, "ESKIZ_PASSWORD", "")
        self.sender = getattr(settings, "ESKIZ_FROM", "4546")
        if not (self.email and self.password):
            raise SmsDeliveryError("Eskiz credentials are not configured.")

    # --- token ---------------------------------------------------------
    def _fetch_token(self) -> str:
        import httpx  # local import: keep dep optional for tests
        try:
            response = httpx.post(
                f"{self.base_url}/auth/login",
                data={"email": self.email, "password": self.password},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network
            raise SmsDeliveryError(f"Eskiz auth failed: {exc}") from exc
        token = payload.get("data", {}).get("token")
        if not token:
            raise SmsDeliveryError("Eskiz auth response missing token.")
        return token

    def _get_token(self) -> str:
        from django.core.cache import cache
        token = cache.get(self.TOKEN_CACHE_KEY)
        if token:
            return token
        token = self._fetch_token()
        cache.set(self.TOKEN_CACHE_KEY, token, self.TOKEN_TTL)
        return token

    # --- send ----------------------------------------------------------
    def send(self, phone: str, message: str) -> None:
        import httpx
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Eskiz expects phone w/o leading "+" and without spaces.
        normalised = phone.lstrip("+").replace(" ", "")
        try:
            response = httpx.post(
                f"{self.base_url}/message/sms/send",
                data={
                    "mobile_phone": normalised,
                    "message": message,
                    "from": self.sender,
                },
                headers=headers,
                timeout=10.0,
            )
        except Exception as exc:  # pragma: no cover - network
            raise SmsDeliveryError(f"Eskiz send failed: {exc}") from exc
        if response.status_code in (401, 403):
            # Token expired mid-flight: refresh once.
            from django.core.cache import cache
            cache.delete(self.TOKEN_CACHE_KEY)
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            response = httpx.post(
                f"{self.base_url}/message/sms/send",
                data={
                    "mobile_phone": normalised,
                    "message": message,
                    "from": self.sender,
                },
                headers=headers,
                timeout=10.0,
            )
        if response.status_code >= 400:
            raise SmsDeliveryError(
                f"Eskiz HTTP {response.status_code}: {response.text[:200]}"
            )
        logger.info("SMS_ESKIZ_SENT | phone=%s | status=%s", phone, response.status_code)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_backend_singleton: Optional[BaseSmsBackend] = None
_backend_lock = threading.Lock()


def _import_class(dotted: str) -> type:
    module_path, _, class_name = dotted.rpartition(".")
    module = import_module(module_path)
    return getattr(module, class_name)


def get_sms_backend() -> BaseSmsBackend:
    """Return the configured SMS backend singleton."""
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton
    with _backend_lock:
        if _backend_singleton is None:
            dotted = getattr(
                settings, "SMS_BACKEND", "apps.common.sms.MemorySmsBackend"
            )
            cls = _import_class(dotted)
            _backend_singleton = cls()
    return _backend_singleton


def reset_sms_backend() -> None:
    """Test helper: drop the cached singleton."""
    global _backend_singleton
    with _backend_lock:
        _backend_singleton = None


def send_sms(phone: str, message: str) -> None:
    """High-level facade used by the OTP views."""
    get_sms_backend().send(phone, message)
