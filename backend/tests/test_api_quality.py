"""
Tests for Step 20 — Production-quality API improvements.

Covers:
    - Custom exception handler (standardised error envelope)
    - Custom renderer (standardised success envelope)
    - Custom pagination (metadata fields)
    - FilterSet classes (date ranges, exact filters)
    - Ordering / sorting
    - Serializer validation improvements
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.test import APIRequestFactory

from config.api.exception_handler import _flatten_errors, custom_exception_handler
from config.api.pagination import StandardPagination
from config.api.renderers import StandardJSONRenderer
from conftest import BookingFactory, ClientFactory, RoomFactory


# ==============================================================================
# EXCEPTION HANDLER
# ==============================================================================


class TestExceptionHandler:
    """Unit tests for custom_exception_handler."""

    def _make_context(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        return {"request": request, "view": None}

    def test_validation_error_envelope(self):
        exc = ValidationError({"name": ["This field is required."]})
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 400
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "validation_error"
        assert "details" in response.data["error"]

    def test_authentication_failed_envelope(self):
        exc = AuthenticationFailed()
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 401
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "authentication_failed"

    def test_not_authenticated_envelope(self):
        exc = NotAuthenticated()
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 401
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "not_authenticated"

    def test_permission_denied_envelope(self):
        exc = PermissionDenied()
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 403
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "permission_denied"

    def test_not_found_envelope(self):
        exc = NotFound()
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 404
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "not_found"

    def test_method_not_allowed_envelope(self):
        exc = MethodNotAllowed("DELETE")
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 405
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "method_not_allowed"

    def test_throttled_envelope(self):
        exc = Throttled(wait=30)
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 429
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "throttled"

    def test_parse_error_envelope(self):
        exc = ParseError()
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 400
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "parse_error"

    def test_unhandled_exception_returns_500(self):
        exc = RuntimeError("boom")
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.data is not None
        assert response.status_code == 500
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "server_error"

    def test_flatten_errors_string(self):
        assert _flatten_errors("Something broke") == "Something broke"

    def test_flatten_errors_list(self):
        result = _flatten_errors(["Error 1.", "Error 2."])
        assert "Error 1." in result
        assert "Error 2." in result

    def test_flatten_errors_dict(self):
        result = _flatten_errors({"field": ["Required."]})
        assert "field" in result
        assert "Required." in result

    def test_flatten_errors_non_field(self):
        result = _flatten_errors({"non_field_errors": ["Bad."]})
        assert "Bad." in result
        # Should not prefix with "non_field_errors:"
        assert "non_field_errors:" not in result


# ==============================================================================
# RENDERER
# ==============================================================================


class TestStandardJSONRenderer:
    """Unit tests for StandardJSONRenderer."""

    def _render(self, data, status_code=200):
        from rest_framework.response import Response as DRFResponse

        renderer = StandardJSONRenderer()
        response = DRFResponse(data, status=status_code)
        response["Content-Type"] = "application/json"
        import json

        raw = renderer.render(data, renderer_context={"response": response})
        return json.loads(raw)

    def test_success_response_wrapped(self):
        result = self._render({"id": 1, "name": "Test"}, status_code=200)
        assert result["success"] is True
        assert result["data"]["id"] == 1

    def test_error_response_not_double_wrapped(self):
        """Error data already has {success: false} from exception handler."""
        error_data = {"success": False, "error": {"code": "not_found"}}
        result = self._render(error_data, status_code=404)
        # Should not wrap again
        assert result["success"] is False
        assert "data" not in result

    def test_already_wrapped_success_not_double_wrapped(self):
        data = {"success": True, "data": {"id": 1}}
        result = self._render(data, status_code=200)
        assert result["success"] is True
        assert result["data"]["id"] == 1

    def test_list_response_wrapped(self):
        result = self._render([1, 2, 3], status_code=200)
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    def test_null_data_wrapped(self):
        result = self._render(None, status_code=204)
        assert result["success"] is True


# ==============================================================================
# PAGINATION
# ==============================================================================


class TestStandardPagination:
    """Unit tests for StandardPagination."""

    def test_page_size_default(self):
        paginator = StandardPagination()
        assert paginator.page_size == 20

    def test_max_page_size(self):
        paginator = StandardPagination()
        assert paginator.max_page_size == 100


# ==============================================================================
# FILTERS & ORDERING — Bookings
# ==============================================================================


@pytest.mark.django_db
class TestBookingFiltersAndOrdering:
    """Integration tests for BookingFilter & ordering on BookingViewSet."""

    def test_filter_by_status(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url, {"status": "pending"})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_by_branch(self, admin_client, booking, branch):
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url, {"branch": branch.pk})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_check_in_after(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        resp = admin_client.get(url, {"check_in_after": yesterday})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_check_in_before(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = admin_client.get(url, {"check_in_before": tomorrow})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_ordering_by_created_at(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url, {"ordering": "-created_at"})
        assert resp.status_code == 200

    def test_ordering_by_final_price(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url, {"ordering": "final_price"})
        assert resp.status_code == 200

    def test_search_by_client_name(self, admin_client, booking):
        url = reverse("bookings:booking-list")
        name_part = booking.client.full_name[:4]
        resp = admin_client.get(url, {"search": name_part})
        assert resp.status_code == 200


# ==============================================================================
# FILTERS & ORDERING — Rooms
# ==============================================================================


@pytest.mark.django_db
class TestRoomFiltersAndOrdering:
    """Integration tests for RoomFilter & ordering on RoomViewSet."""

    def test_filter_by_branch(self, admin_client, room, branch):
        url = reverse("branches:room-list")
        resp = admin_client.get(url, {"branch": branch.pk})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_by_status(self, admin_client, room):
        url = reverse("branches:room-list")
        resp = admin_client.get(url, {"status": "available"})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_filter_by_room_number_icontains(self, admin_client, room):
        url = reverse("branches:room-list")
        resp = admin_client.get(url, {"room_number": room.room_number[:2]})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_ordering_by_room_number(self, admin_client, room):
        url = reverse("branches:room-list")
        resp = admin_client.get(url, {"ordering": "room_number"})
        assert resp.status_code == 200


# ==============================================================================
# STANDARDISED RESPONSE FORMAT — Integration
# ==============================================================================


@pytest.mark.django_db
class TestStandardisedResponses:
    """
    Integration tests verifying the actual JSON body contains
    the standard envelope for both success and error scenarios.
    """

    def test_success_list_has_pagination_metadata(self, admin_client, booking):
        """List endpoint returns count, total_pages, page, page_size, results."""
        url = reverse("bookings:booking-list")
        resp = admin_client.get(url)
        assert resp.status_code == 200
        # response.data is the pagination dict (before renderer wrapping)
        assert "count" in resp.data
        assert "total_pages" in resp.data
        assert "page" in resp.data
        assert "page_size" in resp.data
        assert "results" in resp.data

    def test_success_detail_returns_data(self, admin_client, booking):
        url = reverse("bookings:booking-detail", args=[booking.pk])
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert "id" in resp.data

    def test_error_unauthenticated_has_standard_envelope(self, api_client):
        """Unauthenticated request gets standard error envelope."""
        url = reverse("bookings:booking-list")
        resp = api_client.get(url)
        # With JWTAuthentication providing WWW-Authenticate header,
        # unauthenticated requests return 401 (not 403).
        assert resp.status_code == 401
        assert resp.data["success"] is False
        assert "error" in resp.data
        assert resp.data["error"]["code"] == "not_authenticated"

    def test_error_404_has_standard_envelope(self, admin_client):
        url = reverse("bookings:booking-detail", args=[999999])
        resp = admin_client.get(url)
        assert resp.status_code == 404
        assert resp.data["success"] is False
        assert resp.data["error"]["code"] == "not_found"

    def test_validation_error_has_details(self, admin_client, branch):
        """POST with invalid data returns validation_error with details."""
        url = reverse("bookings:booking-list")
        resp = admin_client.post(url, {}, format="json")
        assert resp.status_code == 400
        assert resp.data["success"] is False
        assert resp.data["error"]["code"] == "validation_error"
        assert "details" in resp.data["error"]

    def test_rendered_json_has_success_wrapper(self, admin_client, booking):
        """The actual JSON bytes contain the {success: true, data: ...} wrapper."""
        import json

        url = reverse("bookings:booking-detail", args=[booking.pk])
        resp = admin_client.get(url)
        body = json.loads(resp.content)
        assert body["success"] is True
        assert "data" in body

    def test_rendered_json_list_has_success_wrapper(self, admin_client, booking):
        import json

        url = reverse("bookings:booking-list")
        resp = admin_client.get(url)
        body = json.loads(resp.content)
        assert body["success"] is True
        assert "data" in body
        assert "results" in body["data"]
        assert "count" in body["data"]


# ==============================================================================
# SERIALIZER VALIDATION
# ==============================================================================


@pytest.mark.django_db
class TestBookingSerializerValidation:
    """Test enhanced BookingSerializer validation."""

    def test_check_out_before_check_in_rejected(
        self, admin_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-08-05",
            "check_out_date": "2026-08-01",  # before check-in
            "price_at_booking": "500000.00",
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400
        assert resp.data["error"]["code"] == "validation_error"

    def test_discount_exceeding_price_rejected(
        self, admin_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-08-01",
            "check_out_date": "2026-08-05",
            "price_at_booking": "100.00",
            "discount_amount": "200.00",  # > price
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400

    def test_zero_price_rejected(
        self, admin_client, client_profile, room, branch,
    ):
        url = reverse("bookings:booking-list")
        payload = {
            "client": client_profile.pk,
            "room": room.pk,
            "branch": branch.pk,
            "check_in_date": "2026-08-01",
            "check_out_date": "2026-08-05",
            "price_at_booking": "0",
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPaymentSerializerValidation:
    """Test enhanced PaymentSerializer validation."""

    def test_zero_amount_rejected(self, admin_client, booking):
        url = reverse("payments:payment-list")
        payload = {
            "booking": booking.pk,
            "amount": "0",
            "payment_type": "manual",
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400

    def test_negative_amount_rejected(self, admin_client, booking):
        url = reverse("payments:payment-list")
        payload = {
            "booking": booking.pk,
            "amount": "-100",
            "payment_type": "manual",
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestShiftAssignmentSerializerValidation:
    """Test enhanced ShiftAssignmentSerializer validation."""

    def test_past_date_rejected(self, director_client, director_profile, account, branch):
        url = reverse("staff:shift-assignment-list")
        payload = {
            "account": account.pk,
            "role": "staff",
            "branch": branch.pk,
            "shift_type": "day",
            "date": "2020-01-01",  # past date
            "assigned_by": director_profile.pk,
        }
        resp = director_client.post(url, payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestRoomSerializerValidation:
    """Test enhanced RoomSerializer validation."""

    def test_blank_room_number_rejected(self, admin_client, branch, room_type):
        url = reverse("branches:room-list")
        payload = {
            "branch": branch.pk,
            "room_type": room_type.pk,
            "room_number": "   ",  # blank
        }
        resp = admin_client.post(url, payload, format="json")
        assert resp.status_code == 400
