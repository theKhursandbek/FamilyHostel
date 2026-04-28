"""Branch / Room filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Room


class RoomFilter(django_filters.FilterSet):
    """Advanced filtering for rooms.

    Supports:
        - branch, room_type, status (exact)
        - is_active (boolean)
        - room_number (contains / icontains)
        - has_active_cleaning (boolean) — when ``False``, excludes any
          room that currently has a non-completed cleaning task. Used by
          the "New Cleaning Task" form so admins can't pick a room that
          is already queued / being cleaned.
    """

    room_number = django_filters.CharFilter(
        field_name="room_number", lookup_expr="icontains",
    )
    has_active_cleaning = django_filters.BooleanFilter(
        method="filter_has_active_cleaning",
    )

    def filter_has_active_cleaning(self, queryset, name, value):
        # Lazy import to avoid a circular dependency at app load.
        from apps.cleaning.models import CleaningTask

        active_room_ids = (
            CleaningTask.objects
            .exclude(status=CleaningTask.TaskStatus.COMPLETED)
            .values_list("room_id", flat=True)
        )
        if value is True:
            return queryset.filter(pk__in=active_room_ids)
        if value is False:
            return queryset.exclude(pk__in=active_room_ids)
        return queryset

    class Meta:
        model = Room
        fields = ["branch", "room_type", "status", "is_active"]
