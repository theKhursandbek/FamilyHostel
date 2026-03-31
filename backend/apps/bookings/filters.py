"""Booking filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Booking


class BookingFilter(django_filters.FilterSet):
    """Advanced filtering for bookings.

    Supports:
        - branch, room, status (exact)
        - client (exact FK)
        - check_in_date / check_out_date range (gte / lte)
        - created_at range (gte / lte)
    """

    check_in_after = django_filters.DateFilter(
        field_name="check_in_date", lookup_expr="gte",
    )
    check_in_before = django_filters.DateFilter(
        field_name="check_in_date", lookup_expr="lte",
    )
    check_out_after = django_filters.DateFilter(
        field_name="check_out_date", lookup_expr="gte",
    )
    check_out_before = django_filters.DateFilter(
        field_name="check_out_date", lookup_expr="lte",
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )

    class Meta:
        model = Booking
        fields = ["branch", "room", "client", "status"]
