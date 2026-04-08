"""Staff filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Attendance, DayOffRequest, ShiftAssignment


class ShiftAssignmentFilter(django_filters.FilterSet):
    """Advanced filtering for shift assignments.

    Supports:
        - branch, shift_type, role, account (exact)
        - date range (gte / lte)
    """

    date_from = django_filters.DateFilter(
        field_name="date", lookup_expr="gte",
    )
    date_to = django_filters.DateFilter(
        field_name="date", lookup_expr="lte",
    )

    class Meta:
        model = ShiftAssignment
        fields = ["branch", "shift_type", "date", "role", "account"]


class AttendanceFilter(django_filters.FilterSet):
    """Advanced filtering for attendance records.

    Supports:
        - branch, shift_type, status, account (exact)
        - date range (gte / lte)
    """

    date_from = django_filters.DateFilter(
        field_name="date", lookup_expr="gte",
    )
    date_to = django_filters.DateFilter(
        field_name="date", lookup_expr="lte",
    )

    class Meta:
        model = Attendance
        fields = ["branch", "shift_type", "date", "status", "account"]


class DayOffRequestFilter(django_filters.FilterSet):
    """Filtering for day-off requests (Step 21.5).

    Supports:
        - status, branch, account (exact)
        - date ranges on start_date / end_date
    """

    start_date_from = django_filters.DateFilter(
        field_name="start_date", lookup_expr="gte",
    )
    start_date_to = django_filters.DateFilter(
        field_name="start_date", lookup_expr="lte",
    )

    class Meta:
        model = DayOffRequest
        fields = ["status", "branch", "account"]
