"""Branch / Room filters (Step 20 — production-quality filtering)."""

import django_filters

from .models import Room


class RoomFilter(django_filters.FilterSet):
    """Advanced filtering for rooms.

    Supports:
        - branch, room_type, status (exact)
        - is_active (boolean)
        - room_number (contains / icontains)
    """

    room_number = django_filters.CharFilter(
        field_name="room_number", lookup_expr="icontains",
    )

    class Meta:
        model = Room
        fields = ["branch", "room_type", "status", "is_active"]
