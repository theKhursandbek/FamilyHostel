"""Payments views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Payment
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD for payments."""

    queryset = Payment.objects.select_related("booking", "created_by")
    serializer_class = PaymentSerializer
    permission_classes = [AllowAny]  # TODO: restrict to Administrator
    filterset_fields = ["booking", "is_paid", "payment_type"]
