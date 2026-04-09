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
        phone = attrs.get("phone", "").strip()
        password = attrs.get("password", "")

        # Find account by phone number
        try:
            account = Account.objects.get(phone=phone)
        except Account.DoesNotExist:
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

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": account.id,
                    "phone": account.phone,
                    "telegram_id": account.telegram_id,
                    "roles": account.roles,
                },
            },
            status=status.HTTP_200_OK,
        )
