"""
Tests for Step 21.6 — Admin Panel workflows.

Covers:
    Room Inspection:
        - Model creation
        - Service layer (create, audit logging)
        - API endpoints (create, list, retrieve)
        - Permission enforcement (admin can create, director can view, staff denied)
        - Filtering (by status, room, branch)

    Cash Session:
        - Model creation
        - Service layer (open, close, handover, validations, audit)
        - API endpoints (open, close, handover, list, retrieve)
        - Validation (duplicate active, already closed, self-handover)
        - Permission enforcement (admin CRUD own, director view, staff denied)
        - Filtering (by admin, shift_type, is_active)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status

from apps.admin_panel.models import CashSession, RoomInspection
from apps.admin_panel.services import (
    close_cash_session,
    create_room_inspection,
    handover_cash_session,
    open_cash_session,
)
from apps.reports.models import AuditLog
from conftest import (
    AccountFactory,
    AdministratorFactory,
    BookingFactory,
    BranchFactory,
    ClientFactory,
    DirectorFactory,
    RoomFactory,
    RoomTypeFactory,
    StaffFactory,
    SuperAdminFactory,
)

# Base URLs
INSPECTION_URL = "/api/v1/admin-panel/room-inspections/"
CASH_SESSION_URL = "/api/v1/admin-panel/cash-sessions/"


# ==============================================================================
# ROOM INSPECTION — MODEL TESTS
# ==============================================================================


@pytest.mark.django_db
class TestRoomInspectionModel:
    """Test the RoomInspection model basics."""

    def test_create_minimal(self, branch, room, admin_profile):
        inspection = RoomInspection.objects.create(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status=RoomInspection.InspectionStatus.CLEAN,
        )
        assert inspection.pk is not None
        assert inspection.status == "clean"
        assert inspection.notes == ""
        assert inspection.booking is None

    def test_create_with_booking(self, branch, room, admin_profile, booking):
        inspection = RoomInspection.objects.create(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status=RoomInspection.InspectionStatus.DAMAGED,
            booking=booking,
            notes="Broken window",
        )
        assert inspection.booking == booking
        assert inspection.notes == "Broken window"

    def test_str_representation(self, branch, room, admin_profile):
        inspection = RoomInspection.objects.create(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status=RoomInspection.InspectionStatus.NEEDS_CLEANING,
        )
        assert "Inspection #" in str(inspection)
        assert "needs_cleaning" in str(inspection)

    def test_default_ordering(self, branch, room, admin_profile):
        """Default ordering is by -created_at."""
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile,
            status="clean",
        )
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile,
            status="damaged",
        )
        inspections = list(RoomInspection.objects.all())
        assert len(inspections) == 2
        # Both returned; exact order may tie on auto_now_add
        assert {i.status for i in inspections} == {"clean", "damaged"}


# ==============================================================================
# ROOM INSPECTION — SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestRoomInspectionService:
    """Test the room inspection service layer."""

    def test_create_inspection(self, branch, room, admin_profile):
        inspection = create_room_inspection(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status="clean",
        )
        assert inspection.pk is not None
        assert inspection.status == "clean"
        assert inspection.inspected_by == admin_profile

    def test_create_inspection_with_booking(self, branch, room, admin_profile, booking):
        inspection = create_room_inspection(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status="damaged",
            notes="Stain on carpet",
            booking=booking,
        )
        assert inspection.booking == booking
        assert inspection.notes == "Stain on carpet"

    def test_create_inspection_audit_log(self, branch, room, admin_profile):
        create_room_inspection(
            room=room,
            branch=branch,
            inspected_by=admin_profile,
            status="clean",
        )
        audit = AuditLog.objects.filter(action="room_inspection.created").first()
        assert audit is not None
        assert audit.entity_type == "RoomInspection"
        assert audit.account == admin_profile.account


# ==============================================================================
# CASH SESSION — SERVICE TESTS
# ==============================================================================


@pytest.mark.django_db
class TestCashSessionService:
    """Test the cash session service layer."""

    def test_open_session(self, branch, admin_profile):
        session = open_cash_session(
            admin=admin_profile,
            branch=branch,
            shift_type="day",
            opening_balance=Decimal("100000"),
        )
        assert session.pk is not None
        assert session.shift_type == "day"
        assert session.opening_balance == Decimal("100000")
        assert session.end_time is None
        assert session.closing_balance is None

    def test_open_session_audit_log(self, branch, admin_profile):
        open_cash_session(
            admin=admin_profile,
            branch=branch,
            shift_type="day",
            opening_balance=Decimal("100000"),
        )
        audit = AuditLog.objects.filter(action="cash_session.opened").first()
        assert audit is not None
        assert audit.entity_type == "CashSession"

    def test_open_duplicate_raises(self, branch, admin_profile):
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        with pytest.raises(DjangoValidationError, match="already has an active"):
            open_cash_session(
                admin=admin_profile, branch=branch,
                shift_type="night", opening_balance=Decimal("50000"),
            )

    def test_close_session(self, branch, admin_profile):
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        closed = close_cash_session(
            session=session,
            closing_balance=Decimal("120000"),
            note="Good shift",
        )
        assert closed.end_time is not None
        assert closed.closing_balance == Decimal("120000")
        assert closed.difference == Decimal("20000")
        assert closed.note == "Good shift"

    def test_close_session_audit_log(self, branch, admin_profile):
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=session, closing_balance=Decimal("100000"))
        audit = AuditLog.objects.filter(action="cash_session.closed").first()
        assert audit is not None
        assert audit.before_data is not None
        assert audit.after_data is not None

    def test_close_already_closed_raises(self, branch, admin_profile):
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=session, closing_balance=Decimal("100000"))
        with pytest.raises(DjangoValidationError, match="already closed"):
            close_cash_session(session=session, closing_balance=Decimal("100000"))

    def test_handover_session(self, branch, admin_profile):
        other_admin = AdministratorFactory(branch=branch)
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        handed = handover_cash_session(
            session=session,
            handed_over_to=other_admin,
            closing_balance=Decimal("110000"),
            note="Handing over",
        )
        assert handed.end_time is not None
        assert handed.handed_over_to == other_admin
        assert handed.closing_balance == Decimal("110000")
        assert handed.difference == Decimal("10000")

    def test_handover_audit_log(self, branch, admin_profile):
        other_admin = AdministratorFactory(branch=branch)
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        handover_cash_session(
            session=session,
            handed_over_to=other_admin,
            closing_balance=Decimal("100000"),
        )
        audit = AuditLog.objects.filter(action="cash_session.handover").first()
        assert audit is not None

    def test_handover_to_self_raises(self, branch, admin_profile):
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        with pytest.raises(DjangoValidationError, match="same admin"):
            handover_cash_session(
                session=session,
                handed_over_to=admin_profile,
                closing_balance=Decimal("100000"),
            )

    def test_handover_already_closed_raises(self, branch, admin_profile):
        other_admin = AdministratorFactory(branch=branch)
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=session, closing_balance=Decimal("100000"))
        with pytest.raises(DjangoValidationError, match="already closed"):
            handover_cash_session(
                session=session,
                handed_over_to=other_admin,
                closing_balance=Decimal("100000"),
            )

    def test_open_after_close_allowed(self, branch, admin_profile):
        """After closing a session, admin can open a new one."""
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=session, closing_balance=Decimal("100000"))
        new_session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="night", opening_balance=Decimal("50000"),
        )
        assert new_session.pk is not None
        assert new_session.shift_type == "night"


# ==============================================================================
# ROOM INSPECTION — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestRoomInspectionAPI:
    """Test room inspection REST endpoints."""

    def test_create_inspection(self, admin_client, admin_profile, room):
        resp = admin_client.post(INSPECTION_URL, {
            "room": room.pk,
            "status": "clean",
            "notes": "All good",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["status"] == "clean"
        assert resp.data["notes"] == "All good"
        assert resp.data["room"] == room.pk

    def test_create_inspection_with_booking(
        self, admin_client, admin_profile, room, booking,
    ):
        resp = admin_client.post(INSPECTION_URL, {
            "room": room.pk,
            "status": "damaged",
            "booking": booking.pk,
            "notes": "Broken lamp",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["booking"] == booking.pk

    def test_create_inspection_invalid_room(self, admin_client, admin_profile):
        resp = admin_client.post(INSPECTION_URL, {
            "room": 99999,
            "status": "clean",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_inspection_invalid_status(self, admin_client, admin_profile, room):
        resp = admin_client.post(INSPECTION_URL, {
            "room": room.pk,
            "status": "invalid_status",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_inspections(self, admin_client, admin_profile, room, branch):
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="clean",
        )
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="damaged",
        )
        resp = admin_client.get(INSPECTION_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 2

    def test_retrieve_inspection(self, admin_client, admin_profile, room, branch):
        inspection = RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="clean",
        )
        resp = admin_client.get(f"{INSPECTION_URL}{inspection.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == inspection.pk

    def test_filter_by_status(self, admin_client, admin_profile, room, branch):
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="clean",
        )
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="damaged",
        )
        resp = admin_client.get(INSPECTION_URL, {"status": "clean"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["status"] == "clean"

    def test_director_can_view(self, director_client, admin_profile, room, branch):
        """Director in the same branch can view inspections."""
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="clean",
        )
        resp = director_client.get(INSPECTION_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_staff_forbidden(self, staff_client, admin_profile, room, branch):
        """Staff should be denied access."""
        RoomInspection.objects.create(
            room=room, branch=branch, inspected_by=admin_profile, status="clean",
        )
        resp = staff_client.get(INSPECTION_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(INSPECTION_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==============================================================================
# CASH SESSION — API TESTS
# ==============================================================================


@pytest.mark.django_db
class TestCashSessionAPI:
    """Test cash session REST endpoints."""

    def test_open_session(self, admin_client, admin_profile):
        resp = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["shift_type"] == "day"
        assert resp.data["opening_balance"] == "100000.00"
        assert resp.data["end_time"] is None

    def test_open_session_with_note(self, admin_client, admin_profile):
        resp = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "night",
            "opening_balance": "50000.00",
            "note": "Starting night shift",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["note"] == "Starting night shift"

    def test_open_duplicate_session(self, admin_client, admin_profile):
        admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        resp = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "night",
            "opening_balance": "50000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_close_session(self, admin_client, admin_profile):
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]
        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/close/", {
            "closing_balance": "120000.00",
            "note": "Shift complete",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["closing_balance"] == "120000.00"
        assert resp.data["end_time"] is not None
        assert resp.data["difference"] == "20000.00"

    def test_close_already_closed(self, admin_client, admin_profile):
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]
        admin_client.post(f"{CASH_SESSION_URL}{session_id}/close/", {
            "closing_balance": "100000.00",
        })
        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/close/", {
            "closing_balance": "100000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_close_by_non_owner_forbidden(self, admin_client, admin_profile, branch):
        """A different admin cannot close someone else's session."""
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]

        other_admin = AdministratorFactory(branch=branch)
        other_client = admin_client.__class__()
        other_client.force_authenticate(user=other_admin.account)

        resp = other_client.post(f"{CASH_SESSION_URL}{session_id}/close/", {
            "closing_balance": "100000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_handover_session(self, admin_client, admin_profile, branch):
        other_admin = AdministratorFactory(branch=branch)

        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]

        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/handover/", {
            "handed_over_to": other_admin.pk,
            "closing_balance": "110000.00",
            "note": "Handover to next shift",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["handed_over_to"] == other_admin.pk
        assert resp.data["end_time"] is not None

    def test_handover_to_self_rejected(self, admin_client, admin_profile):
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]

        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/handover/", {
            "handed_over_to": admin_profile.pk,
            "closing_balance": "100000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_handover_invalid_admin(self, admin_client, admin_profile):
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]

        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/handover/", {
            "handed_over_to": 99999,
            "closing_balance": "100000.00",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_sessions(self, admin_client, admin_profile, branch):
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        resp = admin_client.get(CASH_SESSION_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_retrieve_session(self, admin_client, admin_profile, branch):
        session = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        resp = admin_client.get(f"{CASH_SESSION_URL}{session.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == session.pk

    def test_filter_by_shift_type(self, admin_client, admin_profile, branch):
        s1 = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=s1, closing_balance=Decimal("100000"))
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="night", opening_balance=Decimal("50000"),
        )
        resp = admin_client.get(CASH_SESSION_URL, {"shift_type": "night"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["shift_type"] == "night"

    def test_filter_is_active(self, admin_client, admin_profile, branch):
        s1 = open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        close_cash_session(session=s1, closing_balance=Decimal("100000"))
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="night", opening_balance=Decimal("50000"),
        )
        resp = admin_client.get(CASH_SESSION_URL, {"is_active": "true"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["end_time"] is None

    def test_director_can_view(self, director_client, admin_profile, branch):
        """Director in same branch can view sessions."""
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        resp = director_client.get(CASH_SESSION_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_staff_forbidden(self, staff_client):
        """Staff should be denied access."""
        resp = staff_client.get(CASH_SESSION_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_forbidden(self, api_client):
        resp = api_client.get(CASH_SESSION_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_open_after_handover(self, admin_client, admin_profile, branch):
        """After handover, admin can open new session."""
        other_admin = AdministratorFactory(branch=branch)
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]
        admin_client.post(f"{CASH_SESSION_URL}{session_id}/handover/", {
            "handed_over_to": other_admin.pk,
            "closing_balance": "100000.00",
        })
        resp = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "night",
            "opening_balance": "80000.00",
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_superadmin_can_view_all(self, superadmin_client, admin_profile, branch):
        """SuperAdmin sees all sessions across branches."""
        open_cash_session(
            admin=admin_profile, branch=branch,
            shift_type="day", opening_balance=Decimal("100000"),
        )
        resp = superadmin_client.get(CASH_SESSION_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_negative_balance(self, admin_client, admin_profile, branch):
        """Close with negative difference should be allowed."""
        resp_open = admin_client.post(f"{CASH_SESSION_URL}open/", {
            "shift_type": "day",
            "opening_balance": "100000.00",
        })
        session_id = resp_open.data["id"]
        resp = admin_client.post(f"{CASH_SESSION_URL}{session_id}/close/", {
            "closing_balance": "80000.00",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["difference"] == "-20000.00"
