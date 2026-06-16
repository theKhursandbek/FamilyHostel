"""
Public read-only endpoints for the Telegram Mini App.

Telegram Mini App plan:
  * §4.1  – ``/public/rooms/`` with filters + cursor pagination.
  * §4.5  – queryset shape and validation pipeline.
  * D17   – cursor pagination keyed on
    ``(branch__name, base_price, room_number, id)``, page size 20.
"""

from datetime import date

from django.db.models import Exists, F, OuterRef
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.branches.models import Branch, Room, RoomType
from apps.branches.serializers import (
    BranchSerializer,
    RoomListSerializer,
    RoomSerializer,
    RoomTypeSerializer,
)
from apps.common.validators import (
    validate_csv_choice,
    validate_csv_int,
    validate_decimal,
)


class CatalogueCursorPagination(CursorPagination):
    """Stable ordering for the catalogue infinite scroll (D17)."""

    page_size = 20
    max_page_size = 50
    page_size_query_param = "page_size"
    # Cursor pagination needs the ordering attributes to exist on each instance.
    # We annotate ``branch_name`` from ``branch.name`` in ``get_queryset``.
    ordering = ("branch_name", "base_price", "room_number", "id")


class PublicBranchViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/public/branches/ — active branches only."""

    queryset = Branch.objects.filter(is_active=True).order_by("name")
    serializer_class = BranchSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []  # Anonymous catalogue browsing — no rate cap.
    pagination_class = None


class PublicRoomTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/public/room-types/ — populates the type filter.

    Returns every room type the CEO has created via the admin panel.
    The catalogue room-type filter is meant to mirror what the CEO can
    offer, so freshly-created types must appear even before any room of
    that type exists.
    """

    queryset = RoomType.objects.filter(rooms__isnull=False).distinct().order_by("name")
    serializer_class = RoomTypeSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []
    pagination_class = None


class PublicLocationsView(APIView):
    """GET /api/v1/public/locations/ — controlled enum (D14).

    Returns ``[{code, label, active}]`` for every member of
    ``Branch.Location``; ``active`` reports whether at least one active
    branch currently uses that code so the UI can grey-out empty filters.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        active_codes = set(
            Branch.objects.filter(is_active=True)
            .exclude(location_code="")
            .values_list("location_code", flat=True)
        )
        data = [
            {"code": value, "label": label, "active": value in active_codes}
            for value, label in Branch.Location.choices
        ]
        return Response(data)


class PublicRoomViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/public/rooms/ — catalogue grid for the Mini App."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []  # Anonymous catalogue browsing — no rate cap.
    pagination_class = CatalogueCursorPagination
    serializer_class = RoomListSerializer

    def get_serializer_class(self):
        if self.action == "list":
            return RoomListSerializer
        return RoomSerializer

    def get_queryset(self):
        qs = (
            Room.objects.filter(is_active=True, branch__is_active=True)
            .select_related("branch", "room_type")
            .prefetch_related("images")
        )

        # Detail view bypasses list filters so deep links keep working.
        if self.action != "list":
            return qs

        params = self.request.query_params
        errors: dict[str, list[str]] = {}

        # ``available`` — only rooms in stock and not currently paid-booked.
        available_raw = params.get("available", "true").lower()
        if available_raw not in {"true", "false"}:
            errors["available"] = ["invalid_bool"]
        elif available_raw == "true":
            from apps.bookings.models import Booking

            today = date.today()
            blocked = list(
                Booking.objects.filter(
                    status=Booking.BookingStatus.PAID,
                    check_out_date__gte=today,
                ).values_list("room_id", flat=True)
            )
            qs = qs.filter(status=Room.RoomStatus.AVAILABLE).exclude(id__in=blocked)

        # Price filters.
        price_min = price_max = None
        if params.get("price_min") not in (None, ""):
            try:
                price_min = validate_decimal(
                    params["price_min"], field="price_min", min_value=0
                )
            except ValidationError as exc:
                errors["price_min"] = [str(d) for d in exc.detail]
        if params.get("price_max") not in (None, ""):
            try:
                price_max = validate_decimal(
                    params["price_max"], field="price_max", min_value=0
                )
            except ValidationError as exc:
                errors["price_max"] = [str(d) for d in exc.detail]
        if price_min is not None and price_max is not None and price_min > price_max:
            errors.setdefault("price_min", []).append("range_inverted")

        branch_ids: list[int] = []
        room_type_ids: list[int] = []
        location_codes: list[str] = []
        if params.get("branch"):
            try:
                branch_ids = validate_csv_int(params["branch"], field="branch")
            except ValidationError as exc:
                errors["branch"] = [str(d) for d in exc.detail]
        if params.get("room_type"):
            try:
                room_type_ids = validate_csv_int(
                    params["room_type"], field="room_type"
                )
            except ValidationError as exc:
                errors["room_type"] = [str(d) for d in exc.detail]
        if params.get("location"):
            try:
                location_codes = validate_csv_choice(
                    params["location"],
                    field="location",
                    choices=Branch.Location.values,
                )
            except ValidationError as exc:
                errors["location"] = [str(d) for d in exc.detail]

        if errors:
            raise ValidationError(errors)

        if price_min is not None:
            qs = qs.filter(base_price__gte=price_min)
        if price_max is not None:
            qs = qs.filter(base_price__lte=price_max)
        if branch_ids:
            qs = qs.filter(branch_id__in=branch_ids)
        if room_type_ids:
            qs = qs.filter(room_type_id__in=room_type_ids)
        if location_codes:
            qs = qs.filter(branch__location_code__in=location_codes)

        # Cursor pagination requires explicit ordering — D17. The annotation
        # exposes ``branch_name`` as an instance attribute (DRF cursor reads it
        # directly off the ``Room`` row).
        return qs.annotate(branch_name=F("branch__name")).order_by(
            "branch_name", "base_price", "room_number", "id"
        )
