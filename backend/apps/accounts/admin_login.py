"""
Admin panel login serializer and view.

Provides email/phone + password authentication for the admin panel.
Returns JWT access + refresh tokens on successful login.
"""

from django.contrib.auth import authenticate

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Account


class AdminLoginSerializer(serializers.Serializer):
    """Validate admin login credentials (phone + password)."""

    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        raw_phone = attrs.get("phone", "")
        password = attrs.get("password", "")

        digits = "".join(ch for ch in raw_phone if ch.isdigit())

        # Try exact matches first (most specific → least specific).
        lookup_order = []
        stripped = raw_phone.strip()
        if stripped:
            lookup_order.append(stripped)
        if digits:
            plus = "+" + digits
            if plus not in lookup_order:
                lookup_order.append(plus)
            if digits not in lookup_order:
                lookup_order.append(digits)

        account = None
        for value in lookup_order:
            account = Account.objects.filter(phone=value).first()
            if account is not None:
                break

        # Last-resort fallback: trailing-digits match — but only when it
        # uniquely identifies one account, to avoid logging into the wrong one.
        if account is None and len(digits) >= 9:
            tail = digits[-9:]
            matches = list(Account.objects.filter(phone__endswith=tail)[:2])
            if len(matches) == 1:
                account = matches[0]

        if account is None:
            raise serializers.ValidationError("Invalid credentials.")

        if not account.has_usable_password():
            raise serializers.ValidationError("Password login not available for this account.")

        if not account.check_password(password):
            raise serializers.ValidationError("Invalid credentials.")

        if not account.is_active:
            raise serializers.ValidationError("Account is deactivated.")

        # Only allow staff-level or above
        if not (account.is_hostel_staff or account.is_administrator
                or account.is_director or account.is_superadmin):
            raise serializers.ValidationError("Access denied. Admin privileges required.")

        attrs["account"] = account
        return attrs


class AdminLoginView(APIView):
    """
    POST /api/v1/auth/login/

    Admin panel login — phone + password → JWT tokens.
    """

    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data: dict = serializer.validated_data  # type: ignore[assignment]
        account = data["account"]
        refresh = RefreshToken.for_user(account)

        # Pull display name + branch from the highest-priority role profile.
        # Order matters: superadmin > director > administrator > staff > client.
        full_name = ""
        branch_id = None
        branch_name = ""
        for attr in (
            "superadmin_profile",
            "director_profile",
            "administrator_profile",
            "staff_profile",
            "client_profile",
        ):
            profile = getattr(account, attr, None)
            if profile is None:
                continue
            full_name = getattr(profile, "full_name", "") or ""
            branch = getattr(profile, "branch", None)
            if branch is not None:
                branch_id = branch.id
                branch_name = getattr(branch, "name", "") or ""
            break

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": account.id,
                    "phone": account.phone,
                    "telegram_id": account.telegram_id,
                    "roles": account.roles,
                    "full_name": full_name,
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                },
            },
            status=status.HTTP_200_OK,
        )
