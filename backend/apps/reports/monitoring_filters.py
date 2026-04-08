"""
Monitoring filters — AuditLog & SuspiciousActivity (SuperAdmin monitoring).

Provides rich filtering for the live activity tracking endpoints:
    - AuditLog: action, entity_type, role, account, date range
    - SuspiciousActivity: activity_type, is_blocked, account, ip_address, date range
"""

from __future__ import annotations

import django_filters

from apps.accounts.models import SuspiciousActivity

from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    """Filtering for audit log records.

    Supports:
        - action, entity_type, role, account (exact)
        - created_at range (gte / lte)
        - entity_id (exact)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "role", "account", "entity_id"]


class SuspiciousActivityFilter(django_filters.FilterSet):
    """Filtering for suspicious activity records.

    Supports:
        - activity_type, is_blocked, account (exact)
        - ip_address (exact)
        - created_at / updated_at range (gte / lte)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )
    updated_after = django_filters.DateTimeFilter(
        field_name="updated_at", lookup_expr="gte",
    )
    updated_before = django_filters.DateTimeFilter(
        field_name="updated_at", lookup_expr="lte",
    )

    class Meta:
        model = SuspiciousActivity
        fields = ["activity_type", "is_blocked", "account", "ip_address"]
