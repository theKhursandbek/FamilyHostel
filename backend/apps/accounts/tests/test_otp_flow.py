"""
OTP onboarding flow tests (TELEGRAM_MINI_APP_PLAN.md §3.1, §4.1).
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account, Client, OtpToken
from apps.common.sms import MemorySmsBackend, reset_sms_backend


PHONE = "+998901234567"


@pytest.fixture(autouse=True)
def _sms_backend(settings):
    settings.SMS_BACKEND = "apps.common.sms.MemorySmsBackend"
    reset_sms_backend()
    MemorySmsBackend.clear()
    yield
    MemorySmsBackend.clear()
    reset_sms_backend()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def account_with_client(db):
    account = Account.objects.create(
        telegram_id=987654321,
        phone=PHONE,
        is_active=True,
    )
    Client.objects.create(account=account, full_name="Onboarding Tester")
    return account


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhoneOtpStart:
    URL = "/api/v1/auth/telegram/phone/start/"

    def test_dispatches_sms_and_creates_token(self, api):
        response = api.post(self.URL, {"phone": PHONE}, format="json")
        assert response.status_code == 202, response.content
        assert OtpToken.objects.filter(phone=PHONE, consumed_at__isnull=True).count() == 1
        sent = MemorySmsBackend.last_for(PHONE)
        assert sent is not None
        assert "verification code" in sent["message"].lower()

    def test_normalises_phone_with_spaces(self, api):
        response = api.post(self.URL, {"phone": "+998 90 123 45 67"}, format="json")
        assert response.status_code == 202
        assert OtpToken.objects.filter(phone=PHONE).exists()

    def test_rejects_garbage_phone(self, api):
        response = api.post(self.URL, {"phone": "not-a-number"}, format="json")
        assert response.status_code == 400

    def test_blocks_after_too_many_active_codes(self, api, settings):
        for _ in range(settings.OTP_MAX_ACTIVE_PER_PHONE):
            OtpToken.objects.create(
                phone=PHONE,
                code_hash="x" * 64,
                expires_at=timezone.now() + timedelta(minutes=5),
            )
        response = api.post(self.URL, {"phone": PHONE}, format="json")
        assert response.status_code == 429


# ---------------------------------------------------------------------------
# /verify
# ---------------------------------------------------------------------------

def _seed_token(code="123456", phone=PHONE, **overrides):
    return OtpToken.objects.create(
        phone=phone,
        code_hash=hashlib.sha256(code.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(minutes=5),
        **overrides,
    )


@pytest.mark.django_db
class TestPhoneOtpVerify:
    URL = "/api/v1/auth/telegram/phone/verify/"

    def test_marks_phone_verified(self, api, account_with_client):
        _seed_token()
        response = api.post(
            self.URL,
            {"phone": PHONE, "code": "123456"},
            format="json",
        )
        assert response.status_code == 200, response.content
        body = response.json()["data"] if isinstance(response.json(), dict) and "data" in response.json() else response.json()
        assert body["verified"] is True
        account_with_client.client_profile.refresh_from_db()
        assert account_with_client.client_profile.phone_verified is True

    def test_wrong_code_increments_attempts(self, api):
        token = _seed_token()
        response = api.post(
            self.URL, {"phone": PHONE, "code": "000000"}, format="json"
        )
        assert response.status_code == 400
        token.refresh_from_db()
        assert token.attempts == 1
        assert token.consumed_at is None

    def test_no_active_code(self, api):
        response = api.post(
            self.URL, {"phone": PHONE, "code": "123456"}, format="json"
        )
        assert response.status_code == 400

    def test_consumed_token_rejected_on_second_use(self, api, account_with_client):
        _seed_token()
        first = api.post(self.URL, {"phone": PHONE, "code": "123456"}, format="json")
        assert first.status_code == 200
        second = api.post(self.URL, {"phone": PHONE, "code": "123456"}, format="json")
        assert second.status_code == 400

    def test_too_many_attempts_locks(self, api, settings):
        token = _seed_token()
        token.attempts = settings.OTP_MAX_ATTEMPTS
        token.save(update_fields=["attempts"])
        response = api.post(
            self.URL, {"phone": PHONE, "code": "000000"}, format="json"
        )
        assert response.status_code == 429
