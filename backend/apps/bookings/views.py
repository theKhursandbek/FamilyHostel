"""Bookings views (README Section 17)."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher

from .models import Booking
from .serializers import BookingListSerializer, BookingSerializer
from .services import cancel_booking, complete_booking, create_booking


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

    queryset = Booking.objects.select_related("client", "room", "branch")
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_fields = ["branch", "room", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return BookingListSerializer
        return BookingSerializer

    def perform_create(self, serializer):
        """Delegate creation to the service layer."""
        data = serializer.validated_data
        booking = create_booking(
            client=data["client"],
            room=data["room"],
            branch=data["branch"],
            check_in_date=data["check_in_date"],
            check_out_date=data["check_out_date"],
            price_at_booking=data["price_at_booking"],
            discount_amount=data.get("discount_amount", 0),
        )
        serializer.instance = booking

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /bookings/{pk}/cancel/ — cancel a pending booking."""
        booking = self.get_object()
        booking = cancel_booking(booking)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """POST /bookings/{pk}/complete/ — complete a paid booking."""
        booking = self.get_object()
        booking = complete_booking(booking)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
