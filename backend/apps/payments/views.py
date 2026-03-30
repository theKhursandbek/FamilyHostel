"""Payments views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminOrHigher

from .models import Payment
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD for payments.

    - Admin / Director / SuperAdmin can create and view payments.
    - Staff and Clients have no payment management access.
    """

    queryset = Payment.objects.select_related("booking", "created_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_fields = ["booking", "is_paid", "payment_type"]
