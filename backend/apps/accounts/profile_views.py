"""
Telegram Mini App user-profile endpoints.

    GET  /api/v1/auth/me/        — current account snapshot
    POST /api/v1/auth/profile/   — clients onboard (full_name, phone, language)
"""

from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Account, Client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _branch_for(account: Account):
    """Pick the most relevant branch for a multi-role account."""
    for attr in (
        "director_profile",
        "administrator_profile",
        "staff_profile",
    ):
        prof = getattr(account, attr, None)
        if prof is not None and getattr(prof, "branch_id", None):
            return prof.branch
    return None


def _account_payload(account: Account) -> dict:
    branch = _branch_for(account)
    client = getattr(account, "client_profile", None)
    full_name = client.full_name if client else ""
    parts = full_name.split(" ", 1) if full_name else ["", ""]
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    return {
        "account_id": account.pk,
        "telegram_id": account.telegram_id,
        "phone": account.phone or "",
        "is_active": account.is_active,
        "roles": account.roles,
        "is_new": False,
        "branch_id": branch.pk if branch else None,
        "branch_name": branch.name if branch else None,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "passport_number": getattr(client, "passport_number", "") or "",
        "date_of_birth": (
            client.date_of_birth.isoformat()
            if client and client.date_of_birth else None
        ),
        "language": getattr(account, "language", None) or "ru",
    }


# ---------------------------------------------------------------------------
# /auth/me/
# ---------------------------------------------------------------------------

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_account_payload(request.user))


# ---------------------------------------------------------------------------
# /auth/profile/
# ---------------------------------------------------------------------------

class _ProfileInput(serializers.Serializer):
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    passport_number = serializers.CharField(
        max_length=64, required=False, allow_blank=True,
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    language = serializers.ChoiceField(
        choices=["ru", "en", "uz"], required=False,
    )


class CompleteProfileView(APIView):
    """Clients fill in or update their profile details."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = _ProfileInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account: Account = request.user
        update_account_fields = []
        if "phone" in data and data["phone"] is not None:
            account.phone = data["phone"]
            update_account_fields.append("phone")
        if data.get("language"):
            account.language = data["language"]
            update_account_fields.append("language")
        if update_account_fields:
            update_account_fields.append("updated_at")
            account.save(update_fields=update_account_fields)

        # Resolve full_name from explicit value or first/last fallback.
        full_name = data.get("full_name") or ""
        if not full_name:
            parts = [data.get("first_name", ""), data.get("last_name", "")]
            full_name = " ".join(p.strip() for p in parts if p and p.strip())

        client = getattr(account, "client_profile", None)
        if client is None:
            client = Client.objects.create(
                account=account,
                full_name=full_name or f"User {account.telegram_id or account.pk}",
            )

        update_fields = []
        if full_name:
            client.full_name = full_name
            update_fields.append("full_name")
        if "passport_number" in data:
            client.passport_number = data.get("passport_number") or ""
            update_fields.append("passport_number")
        if "date_of_birth" in data:
            client.date_of_birth = data.get("date_of_birth")
            update_fields.append("date_of_birth")
        if update_fields:
            client.save(update_fields=update_fields)

        return Response(_account_payload(account), status=status.HTTP_200_OK)
