"""Branches views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Branch, Room, RoomType
from .serializers import (
    BranchSerializer,
    RoomListSerializer,
    RoomSerializer,
    RoomTypeSerializer,
)


class BranchViewSet(viewsets.ModelViewSet):
    """CRUD for branches."""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [AllowAny]  # TODO: restrict to Director/SuperAdmin


class RoomTypeViewSet(viewsets.ModelViewSet):
    """CRUD for room types."""

    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [AllowAny]  # TODO: restrict


class RoomViewSet(viewsets.ModelViewSet):
    """CRUD for rooms with nested images on detail."""

    queryset = Room.objects.select_related("branch", "room_type").prefetch_related("images")
    permission_classes = [AllowAny]  # TODO: restrict
    filterset_fields = ["branch", "status", "is_active"]

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer
