"""Bookings views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Booking
from .serializers import BookingListSerializer, BookingSerializer


class BookingViewSet(viewsets.ModelViewSet):
    """CRUD for bookings."""

    queryset = Booking.objects.select_related("client", "room", "branch")
    permission_classes = [AllowAny]  # TODO: role-based permissions
    filterset_fields = ["branch", "room", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return BookingListSerializer
        return BookingSerializer
