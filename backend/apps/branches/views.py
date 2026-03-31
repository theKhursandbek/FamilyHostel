"""Branches views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher, IsAnyRole, ReadOnly

from .filters import RoomFilter
from .models import Branch, Room, RoomType
from .serializers import (
    BranchSerializer,
    RoomListSerializer,
    RoomSerializer,
    RoomTypeSerializer,
)


class BranchViewSet(viewsets.ModelViewSet):
    """CRUD for branches.

    - Read: any authenticated role (clients browse branches).
    - Write: Director / Super Admin only.
    """

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    search_fields = ["name", "location"]


class RoomTypeViewSet(viewsets.ModelViewSet):
    """CRUD for room types.

    - Read: any authenticated role.
    - Write: Admin / Director / Super Admin.
    """

    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    ordering_fields = ["name"]
    ordering = ["name"]
    search_fields = ["name"]


class RoomViewSet(viewsets.ModelViewSet):
    """CRUD for rooms with nested images on detail.

    - Read: all roles (Permission Matrix row "View rooms").
    - Write: Admin / Director / Super Admin.
    """

    queryset = Room.objects.select_related("branch", "room_type").prefetch_related("images")
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    filterset_class = RoomFilter
    ordering_fields = ["room_number", "status", "created_at"]
    ordering = ["room_number"]
    search_fields = ["room_number"]

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer
