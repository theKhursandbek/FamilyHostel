"""Payments views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher

from .models import Payment
from .serializers import PaymentSerializer
from .services import record_payment


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD for payments.

    - Admin / Director / SuperAdmin can create and view payments.
    - Staff and Clients have no payment management access.

    Create is fully delegated to the service layer which enforces:
        - idempotency (no double payment)
        - booking status transitions (pending → paid)
    """

    queryset = Payment.objects.select_related("booking", "created_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_fields = ["booking", "is_paid", "payment_type"]

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
