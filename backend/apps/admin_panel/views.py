"""
Admin Panel views — Room Inspections & Cash Sessions (Step 21.6).

Endpoints:
    Room Inspections:
        POST  /api/v1/admin-panel/room-inspections/        — create
        GET   /api/v1/admin-panel/room-inspections/        — list
        GET   /api/v1/admin-panel/room-inspections/{id}/   — retrieve

    Cash Sessions:
        POST  /api/v1/admin-panel/cash-sessions/open/            — open
        POST  /api/v1/admin-panel/cash-sessions/{id}/close/      — close
        POST  /api/v1/admin-panel/cash-sessions/{id}/handover/   — handover
        GET   /api/v1/admin-panel/cash-sessions/                 — list
        GET   /api/v1/admin-panel/cash-sessions/{id}/            — retrieve
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Administrator
from apps.accounts.permissions import IsAdminOrHigher, IsDirectorOrHigher, ReadOnly
from apps.bookings.models import Booking
from apps.branches.models import Room

from .filters import CashSessionFilter, RoomInspectionFilter
from .models import CashSession, RoomInspection
from .serializers import (
    CashSessionSerializer,
    CloseCashSessionSerializer,
    CreateRoomInspectionSerializer,
    HandoverCashSessionSerializer,
    OpenCashSessionSerializer,
    RoomInspectionSerializer,
)
from .services import (
    close_cash_session,
    create_room_inspection,
    handover_cash_session,
    open_cash_session,
)


class RoomInspectionViewSet(viewsets.GenericViewSet):
    """
    Room inspection CRUD.

    Permission Matrix:
        - Admin: create & view branch inspections
        - Director+: view branch inspections
    """

    serializer_class = RoomInspectionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = RoomInspectionFilter
    ordering_fields = ["created_at", "status", "room"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = RoomInspection.objects.select_related(
            "room", "branch", "inspected_by", "booking",
        ).prefetch_related("images")

        if user.is_superadmin:
            return qs
        if user.is_director:
            director = user.director_profile  # type: ignore[union-attr]
            return qs.filter(branch=director.branch)
        if user.is_administrator:
            admin = user.administrator_profile  # type: ignore[union-attr]
            return qs.filter(branch=admin.branch)
        return qs.none()

    def list(self, request, *args, **kwargs):
        """GET /room-inspections/ — list with filtering."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /room-inspections/{id}/ — single inspection."""
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        """POST /room-inspections/ — create a new inspection."""
        serializer = CreateRoomInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admin_profile = self._resolve_admin(request.user)
        if admin_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Administrator profile not found."},
            )

        # Resolve room
        try:
            room = Room.objects.get(pk=serializer.validated_data["room"])
        except Room.DoesNotExist:
            raise drf_serializers.ValidationError({"room": "Room not found."})

        # Resolve optional booking
        booking = None
        booking_id = serializer.validated_data.get("booking")
        if booking_id is not None:
            try:
                booking = Booking.objects.get(pk=booking_id)
            except Booking.DoesNotExist:
                raise drf_serializers.ValidationError(
                    {"booking": "Booking not found."},
                )

        try:
            inspection = create_room_inspection(
                room=room,
                branch=admin_profile.branch,
                inspected_by=admin_profile,
                status=serializer.validated_data["status"],
                notes=serializer.validated_data.get("notes", ""),
                booking=booking,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(
            RoomInspectionSerializer(inspection).data,
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_admin(user):
        """Return the Administrator profile for the user (or None)."""
        return getattr(user, "administrator_profile", None)


class CashSessionViewSet(viewsets.GenericViewSet):
    """
    Cash session management.

    Permission Matrix:
        - Admin: open, close, handover own sessions; view own branch
        - Director+: view branch sessions (read-only)
    """

    serializer_class = CashSessionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = CashSessionFilter
    ordering_fields = ["start_time", "end_time", "shift_type"]
    ordering = ["-start_time"]

    def get_queryset(self):
        user = self.request.user
        qs = CashSession.objects.select_related(
            "admin", "branch", "handed_over_to",
        )

        if user.is_superadmin:
            return qs
        if user.is_director:
            director = user.director_profile  # type: ignore[union-attr]
            return qs.filter(branch=director.branch)
        if user.is_administrator:
            admin = user.administrator_profile  # type: ignore[union-attr]
            return qs.filter(branch=admin.branch)
        return qs.none()

    def list(self, request, *args, **kwargs):
        """GET /cash-sessions/ — list with filtering."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /cash-sessions/{id}/ — single session."""
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["post"], url_path="open")
    def open_session(self, request):
        """POST /cash-sessions/open/ — open a new session."""
        serializer = OpenCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admin_profile = self._resolve_admin(request.user)
        if admin_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Administrator profile not found."},
            )

        try:
            session = open_cash_session(
                admin=admin_profile,
                branch=admin_profile.branch,
                shift_type=serializer.validated_data["shift_type"],
                opening_balance=serializer.validated_data["opening_balance"],
                note=serializer.validated_data.get("note", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(
            CashSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="close")
    def close_session(self, request, pk=None):
        """POST /cash-sessions/{id}/close/ — close the session."""
        session = self.get_object()

        # Only the session owner can close
        admin_profile = self._resolve_admin(request.user)
        if admin_profile is None or session.admin_id != admin_profile.pk:  # type: ignore[attr-defined]
            raise drf_serializers.ValidationError(
                {"detail": "Only the session owner can close this session."},
            )

        serializer = CloseCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = close_cash_session(
                session=session,
                closing_balance=serializer.validated_data["closing_balance"],
                note=serializer.validated_data.get("note", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(CashSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="handover")
    def handover_session(self, request, pk=None):
        """POST /cash-sessions/{id}/handover/ — handover to next admin."""
        session = self.get_object()

        # Only the session owner can handover
        admin_profile = self._resolve_admin(request.user)
        if admin_profile is None or session.admin_id != admin_profile.pk:  # type: ignore[attr-defined]
            raise drf_serializers.ValidationError(
                {"detail": "Only the session owner can hand over this session."},
            )

        serializer = HandoverCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Resolve the target administrator
        try:
            target_admin = Administrator.objects.get(
                pk=serializer.validated_data["handed_over_to"],
            )
        except Administrator.DoesNotExist:
            raise drf_serializers.ValidationError(
                {"handed_over_to": "Administrator not found."},
            )

        try:
            session = handover_cash_session(
                session=session,
                handed_over_to=target_admin,
                closing_balance=serializer.validated_data["closing_balance"],
                note=serializer.validated_data.get("note", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(CashSessionSerializer(session).data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_admin(user):
        """Return the Administrator profile for the user (or None)."""
        return getattr(user, "administrator_profile", None)
