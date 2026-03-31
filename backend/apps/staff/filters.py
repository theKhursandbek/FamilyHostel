"""Staff filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Attendance, ShiftAssignment


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
