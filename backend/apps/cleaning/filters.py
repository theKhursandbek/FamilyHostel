"""Cleaning task filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import CleaningTask


class CleaningTaskFilter(django_filters.FilterSet):
    """Advanced filtering for cleaning tasks.

    Supports:
        - branch, room, status, priority, assigned_to (exact)
        - created_at range (gte / lte)
        - completed_at range (gte / lte)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )
    completed_after = django_filters.DateTimeFilter(
        field_name="completed_at", lookup_expr="gte",
    )
    completed_before = django_filters.DateTimeFilter(
        field_name="completed_at", lookup_expr="lte",
    )

    class Meta:
        model = CleaningTask
        fields = ["branch", "room", "status", "priority", "assigned_to"]
