"""Branches views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher, IsAnyRole, ReadOnly

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


class RoomTypeViewSet(viewsets.ModelViewSet):
    """CRUD for room types.

    - Read: any authenticated role.
    - Write: Admin / Director / Super Admin.
    """

    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]


class RoomViewSet(viewsets.ModelViewSet):
    """CRUD for rooms with nested images on detail.

    - Read: all roles (Permission Matrix row "View rooms").
    - Write: Admin / Director / Super Admin.
    """

    queryset = Room.objects.select_related("branch", "room_type").prefetch_related("images")
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    filterset_fields = ["branch", "status", "is_active"]

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer
