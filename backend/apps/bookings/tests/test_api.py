"""
Integration tests — Booking API endpoints and permissions.
"""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.bookings.models import Booking

from conftest import ClientFactory, RoomFactory


@pytest.mark.django_db
class TestBookingAPI:
    """Test BookingViewSet CRUD via API."""

    def _booking_payload(self, client_profile, room, branch):
        return {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-08-01",
            "check_out_date": "2026-08-05",
            "price_at_booking": "500000.00",
            "discount_amount": "10000.00",
        }

    def test_admin_can_create_booking(
        self, admin_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = self._booking_payload(client_profile, room, branch)
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["status"] == "pending"
        assert Decimal(resp.data["final_price"]) == Decimal("490000.00")

    def test_admin_can_list_bookings(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_admin_can_cancel_booking(self, admin_client, booking):
        url = reverse("bookings:booking-cancel", args=[booking.pk])
        resp = admin_client.post(url)
        assert resp.status_code == 200
        assert resp.data["status"] == "canceled"

    def test_unauthenticated_cannot_list(self, api_client):
        url = reverse("bookings:booking-list")
        resp = api_client.get(url)
        # JWTAuthentication provides WWW-Authenticate → 401 (not 403)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestBookingPermissions:
    """Test role-based access on booking endpoints."""

    def test_staff_cannot_create_booking(
        self, staff_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-05",
            "price_at_booking": "300000.00",
        }
        resp = staff_client.post(url, payload, format="json")
        assert resp.status_code == 403

    def test_director_can_create_booking(
        self, director_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-10-01",
            "check_out_date": "2026-10-05",
            "price_at_booking": "400000.00",
        }
        resp = director_client.post(url, payload, format="json")
        assert resp.status_code == 201
