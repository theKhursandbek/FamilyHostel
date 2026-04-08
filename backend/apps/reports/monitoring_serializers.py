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

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "account",
            "account_email",
            "role",
            "action",
            "entity_type",
            "entity_id",
            "before_data",
            "after_data",
            "created_at",
        ]
        read_only_fields = fields


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
