"""
Integration tests — Payment API endpoints.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.payments.models import Payment

from conftest import BookingFactory


@pytest.mark.django_db
class TestPaymentAPI:
    """Test PaymentViewSet CRUD via API."""

    def test_admin_can_create_payment(self, admin_client, booking):
        url = reverse("payments:payment-list")
        payload = {
            "booking": booking.pk,
            "amount": "500000.00",
            "payment_type": "manual",
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["is_paid"] is True
        booking.refresh_from_db()
        assert booking.status == "paid"

    def test_staff_cannot_create_payment(self, staff_client, booking):
        url = reverse("payments:payment-list")
        payload = {
            "booking": booking.pk,
            "amount": "500000.00",
            "payment_type": "manual",
        }
        resp = staff_client.post(url, payload, format="json")
        assert resp.status_code == 403

    def test_admin_can_list_payments(self, admin_client):
        url = reverse("payments:payment-list")
        resp = admin_client.get(url)
        assert resp.status_code == 200
