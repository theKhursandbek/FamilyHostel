"""
Client-facing booking views for the Telegram Mini App.

The legacy ``BookingViewSet`` is locked to admin+ roles (it powers the
back-office). Clients can never use it directly. This module exposes a
narrow, client-safe surface:

    GET  /bookings/availability/?room=<id>&from=YYYY-MM-DD&to=YYYY-MM-DD
    GET  /bookings/my/                       — own bookings only
    POST /bookings/my/                       — create as the signed-in client
    GET  /bookings/my/<id>/                  — single own booking
    POST /bookings/my/<id>/cancel/           — cancel own pending booking
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.branches.models import Room

from .models import Booking
from .serializers import BookingSerializer
from .services import cancel_booking, create_booking


def _client_profile(user):
    profile = getattr(user, "client_profile", None)
    if profile is None:
        raise PermissionDenied("Only clients can use this endpoint.")
    return profile


# ---------------------------------------------------------------------------
# Availability — public to *any* authenticated user (clients pre-book)
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def availability(request):
    """GET /bookings/availability/?room=&from=&to=

    Returns ``{"available": bool, "blocked_dates": ["YYYY-MM-DD", …]}``.
    The blocked-dates list covers every active booking on the room within
    a ±90-day window around ``from``, so the calendar can dim them all.
    """
    try:
        room_id = int(request.query_params.get("room") or 0)
    except (TypeError, ValueError):
        raise ValidationError({"room": "Invalid room id."})
    if not room_id:
        raise ValidationError({"room": "room query param is required."})

    from_str = request.query_params.get("from")
    to_str = request.query_params.get("to")
    try:
        from_dt = datetime.strptime(from_str, "%Y-%m-%d").date() if from_str else None
        to_dt = datetime.strptime(to_str, "%Y-%m-%d").date() if to_str else None
    except ValueError:
        raise ValidationError({"detail": "Dates must be YYYY-MM-DD."})

    if not Room.objects.filter(pk=room_id, is_active=True).exists():
        raise NotFound("Room not found.")

    qs = Booking.objects.filter(
        room_id=room_id,
        status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
    )
    if from_dt:
        qs = qs.filter(check_out_date__gte=from_dt)
    if to_dt:
        qs = qs.filter(check_in_date__lte=to_dt)

    blocked = set()
    for b in qs.values_list("check_in_date", "check_out_date"):
        cur = b[0]
        while cur < b[1]:
            blocked.add(cur.isoformat())
            cur = cur.fromordinal(cur.toordinal() + 1)

    available = True
    if from_dt and to_dt:
        # Overlap test
        clash = qs.filter(
            Q(check_in_date__lt=to_dt) & Q(check_out_date__gt=from_dt),
        ).exists()
        available = not clash

    return Response({
        "available": available,
        "blocked_dates": sorted(blocked),
    })


# ---------------------------------------------------------------------------
# Mini App "my bookings" list / create
# ---------------------------------------------------------------------------

class _CreateBookingInput(serializers.Serializer):
    room = serializers.IntegerField()
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0"),
    )

    def validate(self, attrs):
        if attrs["check_out_date"] <= attrs["check_in_date"]:
            raise serializers.ValidationError(
                {"check_out_date": "Check-out must be after check-in."},
            )
        if attrs.get("discount_amount", 0) < 0:
            raise serializers.ValidationError(
                {"discount_amount": "Discount cannot be negative."},
            )
        return attrs


class MyBookingsView(APIView):
    """``GET /bookings/my/`` for clients.

    Booking creation is no longer exposed to the Mini App — clients pay first
    via ``POST /payments/draft/room/`` and the Stripe webhook converts the
    resulting :class:`payments.BookingDraft` into a real Booking (plan §4.1,
    D5). ``POST`` therefore returns ``405 Method Not Allowed``.
    """

    http_method_names = ["get", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _client_profile(request.user)
        qs = (
            Booking.objects
            .filter(client=profile)
            .select_related("room", "branch")
            .order_by("-created_at")
        )
        return Response(BookingSerializer(qs, many=True, context={"request": request}).data)


class MyBookingDetailView(APIView):
    """``GET /bookings/my/<id>/`` and ``POST /bookings/my/<id>/cancel/``."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, request, pk):
        profile = _client_profile(request.user)
        try:
            return Booking.objects.select_related("room", "branch").get(
                pk=pk, client=profile,
            )
        except Booking.DoesNotExist:
            raise NotFound("Booking not found.")

    def get(self, request, pk):
        booking = self._get_object(request, pk)
        return Response(BookingSerializer(booking, context={"request": request}).data)


class MyBookingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _client_profile(request.user)
        try:
            booking = Booking.objects.get(pk=pk, client=profile)
        except Booking.DoesNotExist:
            raise NotFound("Booking not found.")
        try:
            booking = cancel_booking(booking, performed_by=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages},
            )
        return Response(BookingSerializer(booking, context={"request": request}).data)


# Slim ListAPIView fallback (kept for symmetry — `MyBookingsView.get` is
# the canonical implementation). Exposed via urls if ever needed.
class MyBookingsListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = _client_profile(self.request.user)
        return (
            Booking.objects.filter(client=profile)
            .select_related("room", "branch")
            .order_by("-created_at")
        )
