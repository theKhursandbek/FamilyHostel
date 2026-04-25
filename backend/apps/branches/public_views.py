"""
Public read-only endpoints for the Telegram Mini App.

These let prospective clients browse branches and rooms BEFORE registering
(README: "first they can see whole telegram app — branches, rooms..").

Endpoints are intentionally narrow: list + retrieve only, no auth required,
no sensitive data exposed.
"""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.branches.models import Branch, Room
from apps.branches.serializers import (
    BranchSerializer,
    RoomListSerializer,
    RoomSerializer,
)


class PublicBranchViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/public/branches/ — active branches only."""

    queryset = Branch.objects.filter(is_active=True).order_by("name")
    serializer_class = BranchSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None


class PublicRoomViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/public/rooms/?branch=<id> — active rooms.

    Detail view includes images so the mini-app can render a gallery.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None

    def get_queryset(self):
        qs = (
            Room.objects.filter(is_active=True, branch__is_active=True)
            .select_related("branch", "room_type")
            .prefetch_related("images")
            .order_by("room_number")
        )
        branch_id = self.request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer
