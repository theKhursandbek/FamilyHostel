"""Bookings views (README Section 17)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher
from apps.accounts.branch_scope import enforce_branch_on_create, scope_queryset_by_branch
from apps.branches.models import Branch, Room

from .filters import BookingFilter
from .models import Booking
from .serializers import (
    BookingListSerializer,
    BookingSerializer,
    CompleteBookingSerializer,
    ExtendBookingSerializer,
    RefundSerializer,
    WalkInBookingSerializer,
)
from .services import (
    cancel_booking,
    complete_booking,
    create_booking,
    create_walkin_booking,
    extend_booking,
)
from apps.payments.services import record_refund


class BookingViewSet(viewsets.ModelViewSet):
    """CRUD for bookings.

    Permission Matrix (README Section 18):
        - Create booking: Admin ✅ | Director ✅ | SuperAdmin ✅ | Staff ❌
        - Read: Admin / Director / SuperAdmin.
        - Clients see their own bookings (to be refined in business logic step).

    Custom actions:
        - POST /bookings/{pk}/cancel/
        - POST /bookings/{pk}/complete/
    """

    queryset = Booking.objects.select_related(
        "client", "room", "room__branch", "branch",
    )
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = BookingFilter
    ordering_fields = ["check_in_date", "check_out_date", "final_price", "status", "created_at"]
    ordering = ["-created_at"]
    search_fields = ["client__full_name", "room__room_number"]

    def get_queryset(self):
        """Restrict to the user's branch (SuperAdmin sees all).

        SuperAdmin may further narrow via ``?branch=<id>`` (handled by the
        django-filter ``BookingFilter``). For Director / Admin this is
        enforced at the queryset level so they can never see another
        branch's bookings even if they try to bypass the filter.
        """
        qs = super().get_queryset()
        return scope_queryset_by_branch(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return BookingListSerializer
        return BookingSerializer

    def perform_create(self, serializer):
        """Delegate creation to the service layer with branch enforcement."""
        data = serializer.validated_data
        branch = enforce_branch_on_create(self.request.user, data.get("branch"))
        room = data["room"]
        if room.branch_id != branch.pk:
            raise ValidationError(
                {"room": "Selected room does not belong to the chosen branch."}
            )
        booking = create_booking(
            client=data["client"],
            room=room,
            branch=branch,
            check_in_date=data["check_in_date"],
            check_out_date=data["check_out_date"],
            price_at_booking=data["price_at_booking"],
            discount_amount=data.get("discount_amount", 0),
            performed_by=self.request.user,
        )
        serializer.instance = booking

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /bookings/{pk}/cancel/ — cancel a pending booking."""
        booking = self.get_object()
        booking = cancel_booking(booking, performed_by=request.user)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="complete",
        serializer_class=CompleteBookingSerializer,
    )
    def complete(self, request, pk=None):
        """POST /bookings/{pk}/complete/ — DEPRECATED alias for ``checkout``.

        Kept for backward compatibility with older clients.
        """
        return self._do_checkout(request, pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="checkout",
        serializer_class=CompleteBookingSerializer,
    )
    def checkout(self, request, pk=None):
        """POST /bookings/{pk}/checkout/ — check the guest out.

        Per April 2026 rule: early checkout does NOT refund the guest;
        the unused nights are forfeit. Refunds remain possible via the
        explicit ``/refund/`` endpoint (manager discretion, audited).
        """
        return self._do_checkout(request, pk)

    def _do_checkout(self, request, pk):
        booking = self.get_object()
        # We accept the legacy ``refund_amount`` body field but ignore it;
        # validating the serializer keeps API responses consistent.
        serializer = CompleteBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = complete_booking(
                booking,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        return Response(BookingSerializer(booking).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="refund",
        serializer_class=RefundSerializer,
    )
    def refund(self, request, pk=None):
        """POST /bookings/{pk}/refund/ — issue a manual refund (negative payment)."""
        booking = self.get_object()
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record_refund(
                booking=booking,
                amount=serializer.validated_data["amount"],
                reason=serializer.validated_data.get("reason", "manual"),
                created_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        booking.refresh_from_db()
        return Response(BookingSerializer(booking).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="walk-in",
        serializer_class=WalkInBookingSerializer,
    )
    def walk_in(self, request):
        """POST /bookings/walk-in/ — create a new guest + first booking."""
        serializer = WalkInBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            room = Room.objects.select_related("branch").get(pk=data["room"])
        except Room.DoesNotExist:
            raise ValidationError({"room": f"Room with id {data['room']} does not exist."})
        try:
            branch = Branch.objects.get(pk=data["branch"])
        except Branch.DoesNotExist:
            raise ValidationError({"branch": f"Branch with id {data['branch']} does not exist."})
        if room.branch_id != branch.pk:
            raise ValidationError({"room": "Selected room does not belong to the chosen branch."})

        # Branch scoping: Director / Admin can only walk-in for their own branch.
        branch = enforce_branch_on_create(request.user, branch)

        # Price is authoritative on the Room (set at room-creation time).
        # Allow an explicit override only if the caller really sent one.
        price = data.get("price_at_booking") or room.base_price

        try:
            booking = create_walkin_booking(
                full_name=data["full_name"],
                phone=data["phone"],
                passport_number=data["passport_number"],
                room=room,
                branch=branch,
                check_in_date=data["check_in_date"],
                check_out_date=data["check_out_date"],
                price_at_booking=price,
                discount_amount=data.get("discount_amount") or 0,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            # Service layer raises django.core.exceptions.ValidationError —
            # surface it as a clean DRF 400 instead of a generic 500.
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="extend",
        serializer_class=ExtendBookingSerializer,
    )
    def extend(self, request, pk=None):
        """POST /bookings/{pk}/extend/ — push check-out date later."""
        booking = self.get_object()
        serializer = ExtendBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = extend_booking(
                booking=booking,
                new_check_out_date=serializer.validated_data["new_check_out_date"],
                additional_price=serializer.validated_data["additional_price"],
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        return Response(BookingSerializer(booking).data)
