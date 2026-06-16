"""
Client-facing payment views for the Telegram Mini App.

These endpoints handle:
- Room booking payment flow (plan §4.2, D5)
- Extension payment flow
- Guest booking management (phone-based lookup)
- Draft booking status queries
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny


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

    permission_classes = [AllowAny]

    def post(self, request):
        # Placeholder implementation
        return Response({"draft_id": "", "client_secret": ""}, status=status.HTTP_201_CREATED)


class StripeDraftIntentForExtensionView(APIView):
    """POST /payments/draft/extension/ — Create a booking extension draft."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Placeholder implementation
        return Response({"draft_id": "", "client_secret": ""}, status=status.HTTP_201_CREATED)


class BookingDraftStatusView(APIView):
    """GET /payments/drafts/<pk>/ — Check the status of a booking draft."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        # Placeholder implementation
        return Response({"status": "pending"}, status=status.HTTP_200_OK)


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
