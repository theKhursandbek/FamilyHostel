"""Reports filters — Penalties, Facility Logs & Monthly Reports (Step 21.7)."""

import django_filters

from .models import FacilityLog, MonthlyReport, Penalty


class PenaltyFilter(django_filters.FilterSet):
    """Filtering for penalty records.

    Supports:
        - account, type, created_by (exact)
        - created_at range (gte / lte)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )

    class Meta:
        model = Penalty
        fields = ["account", "type", "created_by"]


class FacilityLogFilter(django_filters.FilterSet):
    """Filtering for facility logs.

    Supports:
        - branch, type, status (exact)
        - created_at range (gte / lte)
    """

    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )

    class Meta:
        model = FacilityLog
        fields = ["branch", "type", "status", "shift_type"]


class MonthlyReportFilter(django_filters.FilterSet):
    """Filtering for monthly reports.

    Supports:
        - branch, month, year, created_by (exact)
    """

    class Meta:
        model = MonthlyReport
        fields = ["branch", "month", "year", "created_by"]
