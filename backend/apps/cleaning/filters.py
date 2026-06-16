"""Cleaning task filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import CleaningTask


class CleaningTaskFilter(django_filters.FilterSet):
    """Advanced filtering for cleaning tasks.

    Supports:
        - branch, room, status, priority, assigned_to (exact)
        - created_at range (gte / lte)
        - completed_at range (gte / lte)
        - mine=true → restrict to tasks assigned to the request user
        - status__in=pending,in_progress,retry_required (CSV)
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
    mine = django_filters.BooleanFilter(method="filter_mine")
    status__in = django_filters.BaseInFilter(field_name="status", lookup_expr="in")

    def filter_mine(self, queryset, _name, value):
        if not value:
            return queryset
        request = getattr(self, "request", None)
        user = getattr(request, "user", None)
        staff_profile = getattr(user, "staff_profile", None)
        if staff_profile is None:
            return queryset.none()
        return queryset.filter(assigned_to=staff_profile)

    class Meta:
        model = CleaningTask
        fields = ["branch", "room", "status", "priority", "assigned_to"]
