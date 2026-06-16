"""
Client-facing payment views for the Telegram Mini App.

These endpoints handle:
- Room booking payment flow (plan §4.2, D5)
- Extension payment flow
- Guest booking management (phone-based lookup)
- Draft booking status queries
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import BookingDraft, ExtensionDraft

logger = logging.getLogger(__name__)


class StripeIntentView(APIView):
    """POST /payments/stripe/intent/ — Create a Stripe payment intent."""

    permission_classes = [AllowAny]

    def post(self, request):
        # Placeholder implementation
        return Response({"client_secret": ""}, status=status.HTTP_200_OK)


class MyPaymentsView(APIView):
    """GET /payments/my/ — List authenticated user's payments."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Placeholder implementation
        return Response([], status=status.HTTP_200_OK)


class StripeDraftIntentForRoomView(APIView):
    """POST /payments/draft/room/ — Create a booking draft for a room."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.branches.models import Room
        from apps.bookings.models import Booking

        client_profile = getattr(request.user, "client_profile", None)
        if not client_profile:
            return Response({"detail": "Client profile required."}, status=status.HTTP_403_FORBIDDEN)

        room_id = request.data.get("room")
        check_in_str = request.data.get("check_in_date")
        check_out_str = request.data.get("check_out_date")

        # Validate required fields
        if not all([room_id, check_in_str, check_out_str]):
            return Response(
                {"detail": "room, check_in_date, and check_out_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            room = Room.objects.get(pk=room_id)
        except Room.DoesNotExist:
            return Response({"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        from datetime import date as date_cls
        try:
            check_in_date = date_cls.fromisoformat(check_in_str)
            check_out_date = date_cls.fromisoformat(check_out_str)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate dates
        if check_in_date < date_cls.today():
            return Response(
                {"error": {"details": {"check_in_date": "Check-in must be in the future."}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if check_out_date <= check_in_date:
            return Response(
                {"error": {"details": {"check_out_date": "Check-out must be after check-in."}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nights = (check_out_date - check_in_date).days
        amount = Decimal(room.base_price) * nights

        # Check for overlapping paid/pending bookings
        overlap = Booking.objects.filter(
            room=room,
            status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.PAID],
            check_in_date__lt=check_out_date,
            check_out_date__gt=check_in_date,
        ).exists()
        if overlap:
            return Response(
                {"error": {"details": {"room": "Room is not available for those dates."}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotency: reuse existing pending draft for same room+dates
        existing = BookingDraft.objects.filter(
            client=client_profile,
            room=room,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            status=BookingDraft.Status.PENDING,
        ).first()

        if existing:
            # Retrieve the existing intent from Stripe to get the latest client_secret
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                intent = stripe.PaymentIntent.retrieve(existing.payment_intent_id)
                return Response({
                    "draft_id": str(existing.id),
                    "client_secret": intent.client_secret,
                    "currency": existing.currency,
                    "amount": existing.amount,
                }, status=status.HTTP_200_OK)
            except Exception as exc:
                logger.exception("Failed to retrieve Stripe intent for draft %s", existing.id)
                # Fall through to create a new one

        # Create a Stripe PaymentIntent
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe uses minor units
            currency="uzs",
            metadata={
                "room_id": str(room.pk),
                "client_id": str(client_profile.pk),
                "check_in_date": check_in_str,
                "check_out_date": check_out_str,
            },
        )

        draft = BookingDraft.objects.create(
            client=client_profile,
            room=room,
            branch=room.branch,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            amount=amount,
            currency="uzs",
            payment_intent_id=intent.id,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        return Response({
            "draft_id": str(draft.id),
            "client_secret": intent.client_secret,
            "currency": "uzs",
            "amount": amount,
        }, status=status.HTTP_200_OK)


class StripeDraftIntentForExtensionView(APIView):
    """POST /payments/draft/extension/ — Create a booking extension draft."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.bookings.models import Booking

        client_profile = getattr(request.user, "client_profile", None)
        if not client_profile:
            return Response({"detail": "Client profile required."}, status=status.HTTP_403_FORBIDDEN)

        booking_id = request.data.get("booking")
        new_co_str = request.data.get("new_check_out_date")

        if not all([booking_id, new_co_str]):
            return Response(
                {"detail": "booking and new_check_out_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            booking = Booking.objects.get(pk=booking_id, client=client_profile)
        except Booking.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from datetime import date as date_cls
        try:
            new_check_out_date = date_cls.fromisoformat(new_co_str)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate booking status
        if booking.status != Booking.BookingStatus.PAID:
            return Response(
                {"error": {"details": {"booking": "Only paid bookings can be extended."}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate new date
        if new_check_out_date <= booking.check_out_date:
            return Response(
                {"error": {"details": {"new_check_out_date": "New date must be after current check-out."}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extra_nights = (new_check_out_date - booking.check_out_date).days
        amount = Decimal(booking.room.base_price) * extra_nights

        # Create Stripe PaymentIntent
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="uzs",
            metadata={
                "booking_id": str(booking.pk),
                "new_check_out_date": new_co_str,
            },
        )

        draft = ExtensionDraft.objects.create(
            booking=booking,
            new_check_out_date=new_check_out_date,
            amount=amount,
            currency="uzs",
            payment_intent_id=intent.id,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        return Response({
            "draft_id": str(draft.id),
            "client_secret": intent.client_secret,
            "currency": "uzs",
            "amount": amount,
        }, status=status.HTTP_200_OK)


class BookingDraftStatusView(APIView):
    """GET /payments/drafts/<pk>/ — Check the status of a booking or extension draft."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        # Try BookingDraft first
        try:
            draft = BookingDraft.objects.get(pk=pk)
            return Response({
                "status": draft.status,
                "kind": "booking",
                "booking_id": draft.booking_id,
                "failure_reason": draft.failure_reason or None,
            }, status=status.HTTP_200_OK)
        except BookingDraft.DoesNotExist:
            pass

        # Try ExtensionDraft
        try:
            draft = ExtensionDraft.objects.get(pk=pk)
            return Response({
                "status": draft.status,
                "kind": "extension",
                "booking_id": draft.booking_id,
                "failure_reason": draft.failure_reason or None,
            }, status=status.HTTP_200_OK)
        except ExtensionDraft.DoesNotExist:
            pass

        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


class DemoConfirmDraftView(APIView):
    """POST /payments/drafts/<pk>/demo-confirm/ — Confirm a draft in demo mode."""

    permission_classes = [AllowAny]

    def post(self, request, pk):
        # Placeholder implementation
        return Response({"status": "confirmed"}, status=status.HTTP_200_OK)


class GuestBookingsView(APIView):
    """GET /payments/guest/bookings/?phone=... — List bookings by phone number."""

    permission_classes = [AllowAny]

    def get(self, request):
        # Placeholder implementation
        return Response([], status=status.HTTP_200_OK)


class GuestBookingDetailView(APIView):
    """GET /payments/guest/bookings/<id>/ — Get a single booking by phone."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        # Placeholder implementation
        return Response({}, status=status.HTTP_200_OK)


class GuestBookingCancelView(APIView):
    """POST /payments/guest/bookings/<id>/cancel/ — Cancel a booking by phone."""

    permission_classes = [AllowAny]

    def post(self, request, pk):
        # Placeholder implementation
        return Response({}, status=status.HTTP_200_OK)
