"""
Mini App client registration + password login.

    POST /api/v1/auth/register/      — full registration (returns JWT pair)
    POST /api/v1/auth/client/login/  — phone + password login (returns JWT pair)

Notes:
    - ``Account.USERNAME_FIELD`` is ``telegram_id`` (unique). For browser /
      registration paths we synthesize a deterministic ``telegram_id`` from
      the phone number so the same phone always resolves to the same account
      whether the user signs in via Telegram, password, or both.
    - All input fields are required as per the user spec
      (first_name, last_name, dob, passport_number, phone, password,
      confirm_password).
"""

from __future__ import annotations

import hashlib
import logging
import re

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Account, Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"\D+")


def _normalize_phone(raw: str) -> str:
    digits = _PHONE_RE.sub("", raw or "")
    if len(digits) < 9:
        raise serializers.ValidationError({"phone": "Phone number is too short."})
    return "+" + digits


def _synthetic_telegram_id(phone: str) -> int:
    digest = hashlib.sha256(phone.encode("utf-8")).hexdigest()
    # 62-bit positive int — well inside BigIntegerField range.
    return int(digest[:16], 16) & 0x3FFF_FFFF_FFFF_FFFF


def _tokens_for(account: Account) -> dict:
    refresh = RefreshToken.for_user(account)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _account_payload_full(account: Account) -> dict:
    """Lightweight payload returned by register/login (mirrors profile_views)."""
    client = getattr(account, "client_profile", None)
    full_name = client.full_name if client else ""
    parts = full_name.split(" ", 1) if full_name else ["", ""]
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    return {
        "account_id": account.pk,
        "telegram_id": account.telegram_id,
        "phone": account.phone or "",
        "roles": account.roles,
        "is_new": False,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "passport_number": getattr(client, "passport_number", "") or "",
        "date_of_birth": (
            client.date_of_birth.isoformat()
            if client and client.date_of_birth else None
        ),
        "language": getattr(account, "language", None) or "uz",
    }


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

class _RegisterInput(serializers.Serializer):
    first_name = serializers.CharField(max_length=120)
    last_name = serializers.CharField(max_length=120)
    date_of_birth = serializers.DateField()
    passport_number = serializers.CharField(max_length=50)
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True, min_length=6, max_length=128)
    confirm_password = serializers.CharField(write_only=True, min_length=6, max_length=128)
    # Optional: kept for backwards compatibility (ignored server-side).
    otp_code = serializers.CharField(
        max_length=6, required=False, allow_blank=True, default="",
        write_only=True,
    )
    # True when phone was obtained via Telegram.WebApp.requestContact()
    phone_from_telegram = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "passwords_do_not_match"},
            )
        attrs["phone"] = _normalize_phone(attrs["phone"])
        # Passport must be unique among Clients.
        if Client.objects.filter(passport_number=attrs["passport_number"]).exists():
            raise serializers.ValidationError(
                {"passport_number": "passport_already_registered"},
            )
        return attrs


class ClientRegisterView(APIView):
    """``POST /api/v1/auth/register/`` — Mini App client registration.

    Behaviour:
        - If the caller is already authenticated (e.g. Telegram auto-login
          fired and ``is_new=true``), we update their existing Account /
          Client with the supplied details and set the password.
        - Otherwise we create a fresh Account (synthesizing
          ``telegram_id`` from the phone) and a Client.
        - Returns a fresh JWT pair so the frontend always has a valid
          token after registration.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = _RegisterInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return self._do_register(request, data)

    @transaction.atomic
    def _do_register(self, request, data):

        full_name = f"{data['first_name'].strip()} {data['last_name'].strip()}".strip()

        if request.user and request.user.is_authenticated:
            account: Account = request.user
            # Update phone (only if free) and password.
            if account.phone != data["phone"]:
                account.phone = data["phone"]
            account.set_password(data["password"])
            account.save(update_fields=["phone", "password", "updated_at"])
        else:
            # 1) Prefer an EXISTING account already attached to this phone
            #    (e.g. created earlier as a guest checkout with a negative
            #    synthetic telegram_id). Adopting it preserves the user's
            #    prior bookings under their new login.
            account = Account.objects.filter(phone=data["phone"]).first()
            if account is None:
                # 2) Fall back to looking up / creating by the positive
                #    synthetic id derived from phone.
                tg_id = _synthetic_telegram_id(data["phone"])
                account, _created = Account.objects.get_or_create(
                    telegram_id=tg_id,
                    defaults={"phone": data["phone"], "language": "uz"},
                )
            # If the resolved account already has a real password, block
            # silent overwrite — they should log in instead.
            if account.has_usable_password():
                raise serializers.ValidationError(
                    {"phone": "phone_already_registered"},
                )
            account.phone = data["phone"]
            account.set_password(data["password"])
            account.save(update_fields=["phone", "password", "updated_at"])

        client = getattr(account, "client_profile", None)
        phone_from_telegram = bool(data.get("phone_from_telegram", False))
        if client is None:
            client = Client.objects.create(
                account=account,
                full_name=full_name,
                passport_number=data["passport_number"],
                date_of_birth=data["date_of_birth"],
                phone_verified=phone_from_telegram,
            )
        else:
            client.full_name = full_name
            client.passport_number = data["passport_number"]
            client.date_of_birth = data["date_of_birth"]
            if phone_from_telegram:
                client.phone_verified = True
            client.save(update_fields=[
                "full_name", "passport_number", "date_of_birth", "phone_verified",
            ])

        logger.info("CLIENT_REGISTERED account=%s phone=%s", account.pk, account.phone)

        payload = _account_payload_full(account)
        payload.update(_tokens_for(account))
        return Response(payload, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Phone + password login (clients)
# ---------------------------------------------------------------------------

class _ClientLoginInput(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            phone = _normalize_phone(attrs["phone"])
        except serializers.ValidationError:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        # Try exact phone match, then synthetic-id match (handles cases where
        # phone was normalized differently in older records).
        account = Account.objects.filter(phone=phone).first()
        if account is None:
            tg_id = _synthetic_telegram_id(phone)
            account = Account.objects.filter(telegram_id=tg_id).first()

        if account is None or not account.has_usable_password():
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not account.check_password(attrs["password"]):
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not account.is_active:
            raise serializers.ValidationError({"detail": "Account is deactivated."})

        attrs["account"] = account
        return attrs


class ClientLoginView(APIView):
    """``POST /api/v1/auth/client/login/`` — phone + password → JWT pair."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = _ClientLoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        account: Account = serializer.validated_data["account"]
        payload = _account_payload_full(account)
        payload.update(_tokens_for(account))
        return Response(payload, status=status.HTTP_200_OK)
