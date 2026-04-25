"""
Monitoring serializers — AuditLog & SuspiciousActivity (SuperAdmin monitoring).

Read-only serializers for the live activity tracking and monitoring
endpoints consumed by SuperAdmin (and optionally Director scoped to branch).
"""

from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import SuspiciousActivity

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for audit log entries."""

    account_email = serializers.EmailField(
        source="account.email", read_only=True, default=None,
    )
    account_phone = serializers.CharField(
        source="account.phone", read_only=True, default="",
    )
    account_telegram_id = serializers.IntegerField(
        source="account.telegram_id", read_only=True, default=None,
    )
    account_name = serializers.SerializerMethodField()
    is_reversible = serializers.SerializerMethodField()
    restore_state = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "account",
            "account_email",
            "account_phone",
            "account_telegram_id",
            "account_name",
            "role",
            "action",
            "entity_type",
            "entity_id",
            "before_data",
            "after_data",
            "created_at",
            "is_reversible",
            "restore_state",
        ]
        read_only_fields = fields

    @staticmethod
    def get_account_name(obj):
        acc = obj.account
        if not acc:
            return None
        for attr in (
            "superadmin_profile",
            "director_profile",
            "administrator_profile",
            "staff_profile",
            "client_profile",
        ):
            profile = getattr(acc, attr, None)
            if profile and getattr(profile, "full_name", ""):
                return profile.full_name
        return None

    @staticmethod
    def get_is_reversible(obj):
        from .restore_service import RestoreService

        return RestoreService.is_reversible(obj)

    @staticmethod
    def get_restore_state(obj):
        from .restore_service import RestoreService

        if not RestoreService.is_reversible(obj):
            return "not_reversible"
        return RestoreService.state_of(obj)


class SuspiciousActivitySerializer(serializers.ModelSerializer):
    """Read-only serializer for suspicious activity records."""

    account_email = serializers.EmailField(
        source="account.email", read_only=True, default=None,
    )

    class Meta:
        model = SuspiciousActivity
        fields = [
            "id",
            "account",
            "account_email",
            "ip_address",
            "activity_type",
            "count",
            "is_blocked",
            "blocked_until",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
