"""Branches views (README Section 17)."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher, IsAnyRole, ReadOnly
from apps.reports.audit_mixin import AuditedModelViewSetMixin

from .filters import RoomFilter
from .models import Branch, Room, RoomImage, RoomType
from .serializers import (
    BranchSerializer,
    RoomImageSerializer,
    RoomImageUploadSerializer,
    RoomListSerializer,
    RoomSerializer,
    RoomTypeSerializer,
)


class BranchViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """CRUD for branches.

    - Read: any authenticated role (clients browse branches).
    - Write: Director / Super Admin only.
    - Accepts multipart so a hero `image` can be uploaded with the branch.
    """

    audit_entity_type = "Branch"
    audit_action_prefix = "branch"

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    search_fields = ["name", "location"]


class RoomTypeViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """CRUD for room types.

    - Read: any authenticated role.
    - Write: Admin / Director / Super Admin.
    """

    audit_entity_type = "RoomType"
    audit_action_prefix = "room_type"

    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    ordering_fields = ["name"]
    ordering = ["name"]
    search_fields = ["name"]


class RoomViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """CRUD for rooms with nested images on detail.

    - Read: all roles (Permission Matrix row "View rooms").
    - Write: Admin / Director / Super Admin.
    - Extra: `POST /rooms/{id}/images/` accepts up to 3 photos per room
      (`MAX_IMAGES_PER_ROOM`). The total count across uploads is enforced.
    """

    audit_entity_type = "Room"
    audit_action_prefix = "room"

    queryset = Room.objects.select_related("branch", "room_type").prefetch_related("images")
    permission_classes = [IsAuthenticated, ReadOnly | IsAdminOrHigher]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_class = RoomFilter
    ordering_fields = ["room_number", "status", "created_at"]
    ordering = ["room_number"]
    search_fields = ["room_number"]

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="images(?:/(?P<image_pk>[^/.]+))?",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def images(self, request, pk=None, image_pk=None):
        """
        POST   /rooms/{id}/images/             — upload up to 3 photos
        DELETE /rooms/{id}/images/{image_pk}/  — remove a single photo
        """
        room = self.get_object()

        if request.method == "DELETE":
            if not image_pk:
                return Response(
                    {"detail": "Image id is required to delete."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            deleted, _ = RoomImage.objects.filter(room=room, pk=image_pk).delete()
            if not deleted:
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = RoomImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = serializer.validated_data["images"]

        existing = room.images.count()
        cap = RoomImage.MAX_IMAGES_PER_ROOM
        if existing + len(files) > cap:
            return Response(
                {"detail": (
                    f"Room already has {existing} image(s); cannot upload "
                    f"{len(files)} more (max {cap} per room)."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for idx, f in enumerate(files):
            created.append(RoomImage.objects.create(
                room=room,
                image=f,
                is_primary=(existing == 0 and idx == 0),
                display_order=existing + idx,
            ))
        return Response(
            RoomImageSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
