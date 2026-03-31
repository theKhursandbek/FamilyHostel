"""Payment filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Payment


class PaymentFilter(django_filters.FilterSet):
    """Advanced filtering for payments.

    Supports:
        - booking, is_paid, payment_type (exact)
        - amount range (gte / lte)
        - created_at range (gte / lte)
        - paid_at range (gte / lte)
    """

    amount_min = django_filters.NumberFilter(
        field_name="amount", lookup_expr="gte",
    )
    amount_max = django_filters.NumberFilter(
        field_name="amount", lookup_expr="lte",
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte",
    )
    paid_after = django_filters.DateTimeFilter(
        field_name="paid_at", lookup_expr="gte",
    )
    paid_before = django_filters.DateTimeFilter(
        field_name="paid_at", lookup_expr="lte",
    )

    class Meta:
        model = Payment
        fields = ["booking", "is_paid", "payment_type"]
