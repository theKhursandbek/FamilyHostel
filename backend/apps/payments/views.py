"""Payments views (README Section 17, 25.1 & 26.1)."""

import logging

import stripe
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher

from .filters import PaymentFilter
from .models import Payment
from .serializers import PaymentSerializer
from .services import record_payment
from .stripe_service import construct_webhook_event, process_webhook_event

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD for payments.

    - Admin / Director / SuperAdmin can create and view payments.
    - Staff and Clients have no payment management access.

    Create is fully delegated to the service layer which enforces:
        - idempotency (no double payment)
        - booking status transitions (pending → paid)
    """

    queryset = Payment.objects.select_related(
        "booking", "booking__client", "booking__room", "created_by",
    )
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = PaymentFilter
    ordering_fields = ["amount", "is_paid", "payment_type", "created_at", "paid_at"]
    ordering = ["-created_at"]
    search_fields = ["booking__client__full_name", "payment_intent_id"]

    def perform_create(self, serializer):
        """Delegate creation to the service layer."""
        data = serializer.validated_data
        payment = record_payment(
            booking=data["booking"],
            amount=data["amount"],
            payment_type=data["payment_type"],
            created_by=data.get("created_by"),
        )
        serializer.instance = payment


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """
    Stripe webhook receiver (README Section 26.1).

    URL: POST /api/v1/payments/webhook/

    Security:
        - CSRF exempt (external caller)
        - No authentication (Stripe sends raw POST)
        - Signature verified via ``STRIPE_WEBHOOK_SECRET``

    Handled events:
        - ``payment_intent.succeeded``  → mark booking as paid
        - ``payment_intent.payment_failed`` → log failure
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not sig_header:
            return JsonResponse(
                {"error": "Missing Stripe-Signature header."},
                status=400,
            )

        # Verify signature
        try:
            event = construct_webhook_event(payload, sig_header)
        except stripe.error.SignatureVerificationError:
            logger.warning("Stripe webhook: invalid signature.")
            return JsonResponse(
                {"error": "Invalid signature."},
                status=400,
            )
        except ValueError:
            logger.warning("Stripe webhook: invalid payload.")
            return JsonResponse(
                {"error": "Invalid payload."},
                status=400,
            )

        # Process (idempotent)
        was_new = process_webhook_event(event)

        return JsonResponse(
            {
                "status": "ok",
                "event_id": event.id,
                "new": was_new,
            },
            status=200,
        )
