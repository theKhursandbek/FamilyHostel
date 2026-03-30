"""Bookings views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher, ReadOnly

from .models import Booking
from .serializers import BookingListSerializer, BookingSerializer


class BookingViewSet(viewsets.ModelViewSet):
    """CRUD for bookings.

    Permission Matrix (README Section 18):
        - Create booking: Admin ✅ | Director ✅ | SuperAdmin ✅ | Staff ❌
        - Read: Admin / Director / SuperAdmin.
        - Clients see their own bookings (to be refined in business logic step).
    """

    queryset = Booking.objects.select_related("client", "room", "branch")
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_fields = ["branch", "room", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return BookingListSerializer
        return BookingSerializer
