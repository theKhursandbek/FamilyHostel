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
        - action, entity_type, role, account, entity_id (exact)
        - role__in, action__in, entity_type__in (multi-value via comma)
        - created_at range (created_after / created_before)
        - search: case-insensitive substring across action / entity_type
        - user: case-insensitive substring across account email / phone
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )
    role__in = django_filters.BaseInFilter(field_name="role", lookup_expr="in")
    action__in = django_filters.BaseInFilter(
        field_name="action", lookup_expr="in",
    )
    entity_type__in = django_filters.BaseInFilter(
        field_name="entity_type", lookup_expr="in",
    )
    search = django_filters.CharFilter(method="filter_search")
    user = django_filters.CharFilter(method="filter_user")

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "role", "account", "entity_id"]

    @staticmethod
    def filter_search(queryset, _name, value):
        from django.db.models import Q

        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(action__icontains=value) | Q(entity_type__icontains=value),
        )

    @staticmethod
    def filter_user(queryset, _name, value):
        from django.db.models import Q

        value = (value or "").strip()
        if not value:
            return queryset
        q = Q(account__phone__icontains=value)
        if value.isdigit():
            q |= Q(account__telegram_id=int(value))
            q |= Q(account_id=int(value))
        # Match against any profile full_name
        q |= Q(account__staff_profile__full_name__icontains=value)
        q |= Q(account__administrator_profile__full_name__icontains=value)
        q |= Q(account__director_profile__full_name__icontains=value)
        q |= Q(account__superadmin_profile__full_name__icontains=value)
        q |= Q(account__client_profile__full_name__icontains=value)
        return queryset.filter(q).distinct()


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
