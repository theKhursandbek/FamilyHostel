"""Admin Panel filters — Room Inspections & Cash Sessions (Step 21.6)."""

import django_filters

from .models import CashSession, RoomInspection


class RoomInspectionFilter(django_filters.FilterSet):
    """Filtering for room inspections.

    Supports:
        - room, branch, inspected_by, status (exact)
        - created_at range (gte / lte)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )

    class Meta:
        model = RoomInspection
        fields = ["room", "branch", "inspected_by", "status", "booking"]


class CashSessionFilter(django_filters.FilterSet):
    """Filtering for cash sessions.

    Supports:
        - admin, branch, shift_type (exact)
        - start_time range (gte / lte)
        - is_active (open sessions with no end_time)
    """

    started_after = django_filters.DateTimeFilter(
        field_name="start_time", lookup_expr="gte",
    )
    started_before = django_filters.DateTimeFilter(
        field_name="start_time", lookup_expr="lte",
    )
    is_active = django_filters.BooleanFilter(
        method="filter_is_active",
        label="Active (open) sessions",
    )

    class Meta:
        model = CashSession
        fields = ["admin", "branch", "shift_type"]

    @staticmethod
    def filter_is_active(queryset, _name, value):
        """Filter by whether the session is still open."""
        if value:
            return queryset.filter(end_time__isnull=True)
        return queryset.filter(end_time__isnull=False)
