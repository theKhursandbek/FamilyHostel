"""Catalogue (`/public/rooms/`) filter + pagination tests.

Plan: §4.1, §4.5, §11, D17.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.branches.models import Branch, Room, RoomType


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def types(db):
    standard = RoomType.objects.create(name="Standard")
    deluxe = RoomType.objects.create(name="Deluxe")
    return {"standard": standard, "deluxe": deluxe}


@pytest.fixture
def branches(db):
    a = Branch.objects.create(
        name="Alpha", location="Chilanzar 12",
        location_code=Branch.Location.CHILANZAR, location_label="Chilanzar 12",
    )
    b = Branch.objects.create(
        name="Bravo", location="Yunusabad 7",
        location_code=Branch.Location.YUNUSABAD, location_label="Yunusabad 7",
    )
    c = Branch.objects.create(
        name="Charlie", location="Sergeli 1",
        location_code=Branch.Location.SERGELI, location_label="Sergeli 1",
        is_active=False,
    )
    return {"a": a, "b": b, "c": c}


@pytest.fixture
def rooms(branches, types):
    a, b, c = branches["a"], branches["b"], branches["c"]
    std, dlx = types["standard"], types["deluxe"]
    out = []
    # Alpha branch: 3 rooms.
    out.append(Room.objects.create(branch=a, room_type=std, room_number="101", base_price=Decimal("200000")))
    out.append(Room.objects.create(branch=a, room_type=dlx, room_number="102", base_price=Decimal("400000")))
    out.append(Room.objects.create(branch=a, room_type=std, room_number="103", base_price=Decimal("250000")))
    # Bravo: 2 rooms.
    out.append(Room.objects.create(branch=b, room_type=std, room_number="201", base_price=Decimal("180000")))
    out.append(Room.objects.create(branch=b, room_type=dlx, room_number="202", base_price=Decimal("500000")))
    # Charlie (inactive branch) — must never surface.
    out.append(Room.objects.create(branch=c, room_type=std, room_number="301", base_price=Decimal("100000")))
    return out


def _list(client, **params):
    url = reverse("branches_public:public-room-list")
    return client.get(url, params)


def _err_fields(resp):
    """All client error responses are wrapped under ``error.details``."""
    return resp.data.get("error", {}).get("details", {})


def _ids(payload):
    """Cursor pagination wraps results in {next, previous, results}."""
    return [r["id"] for r in payload["results"]]


@pytest.mark.django_db
def test_default_lists_all_active_rooms(client, rooms):
    resp = _list(client)
    assert resp.status_code == 200
    assert "results" in resp.data
    # Charlie's room (inactive branch) must be excluded.
    assert len(resp.data["results"]) == 5


@pytest.mark.django_db
def test_default_sort_branch_then_price_then_number(client, rooms):
    resp = _list(client)
    numbers = [r["room_number"] for r in resp.data["results"]]
    # Alpha rooms first (price asc): 101 (200k), 103 (250k), 102 (400k).
    # Bravo next: 201 (180k), 202 (500k).
    assert numbers == ["101", "103", "102", "201", "202"]


@pytest.mark.django_db
def test_filter_branch_csv(client, branches, rooms):
    resp = _list(client, branch=str(branches["b"].id))
    assert resp.status_code == 200
    assert {r["branch"] for r in resp.data["results"]} == {branches["b"].id}


@pytest.mark.django_db
def test_filter_room_type_csv(client, types, rooms):
    resp = _list(client, room_type=str(types["deluxe"].id))
    assert all(r["room_type"] == types["deluxe"].id for r in resp.data["results"])
    assert len(resp.data["results"]) == 2


@pytest.mark.django_db
def test_filter_price_range(client, rooms):
    resp = _list(client, price_min="200000", price_max="300000")
    assert resp.status_code == 200
    nums = sorted(r["room_number"] for r in resp.data["results"])
    assert nums == ["101", "103"]


@pytest.mark.django_db
def test_filter_location_csv(client, rooms):
    resp = _list(client, location="yunusabad")
    assert {r["branch_location_code"] for r in resp.data["results"]} == {"yunusabad"}


@pytest.mark.django_db
def test_invalid_price_range(client, rooms):
    resp = _list(client, price_min="500000", price_max="100000")
    assert resp.status_code == 400
    assert "price_min" in _err_fields(resp)


@pytest.mark.django_db
def test_invalid_location_choice(client, rooms):
    resp = _list(client, location="atlantis")
    assert resp.status_code == 400
    assert "location" in _err_fields(resp)


@pytest.mark.django_db
def test_invalid_branch_csv(client, rooms):
    resp = _list(client, branch="abc")
    assert resp.status_code == 400
    assert "branch" in _err_fields(resp)


@pytest.mark.django_db
def test_available_excludes_paid_booking(client, branches, types, rooms):
    """A room with an active PAID booking must drop out of the catalogue."""
    from apps.accounts.models import Account, Client as ClientProfile
    from apps.bookings.models import Booking

    account = Account.objects.create(telegram_id=42, phone="+998901112233")
    profile = ClientProfile.objects.create(account=account, full_name="Test Guest")
    today = date.today()
    Booking.objects.create(
        client=profile,
        room=rooms[0],
        branch=rooms[0].branch,
        check_in_date=today,
        check_out_date=today + timedelta(days=2),
        price_at_booking=Decimal("200000"),
        discount_amount=Decimal("0"),
        final_price=Decimal("400000"),
        status=Booking.BookingStatus.PAID,
    )
    resp = _list(client)
    assert rooms[0].id not in [r["id"] for r in resp.data["results"]]


@pytest.mark.django_db
def test_pagination_cursor_navigates(client, branches, types):
    """page_size=2 should slice results and expose a `next` cursor."""
    a = branches["a"]
    std = types["standard"]
    for i in range(5):
        Room.objects.create(
            branch=a, room_type=std, room_number=f"5{i:02d}",
            base_price=Decimal("100000") + Decimal(i),
        )
    resp = _list(client, page_size="2")
    assert resp.status_code == 200
    assert resp.data["next"] is not None
    assert len(resp.data["results"]) == 2

    # Follow the cursor manually.
    next_url = resp.data["next"]
    resp2 = client.get(next_url)
    assert resp2.status_code == 200
    assert len(resp2.data["results"]) == 2


@pytest.mark.django_db
def test_room_type_list_endpoint(client, rooms):
    """Only types that have at least one active room appear in the filter."""
    url = reverse("branches_public:public-room-type-list")
    resp = client.get(url)
    assert resp.status_code == 200
    names = [t["name"] for t in resp.data]
    assert "Standard" in names and "Deluxe" in names


@pytest.mark.django_db
def test_room_type_list_hides_orphan_types(client, types):
    """A RoomType with no rooms attached must NOT appear in the filter."""
    url = reverse("branches_public:public-room-type-list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_locations_endpoint_marks_active(client, branches):
    url = reverse("branches_public:public-locations")
    resp = client.get(url)
    assert resp.status_code == 200
    by_code = {row["code"]: row for row in resp.data}
    # Active branches Alpha+Bravo cover chilanzar+yunusabad.
    assert by_code["chilanzar"]["active"] is True
    assert by_code["yunusabad"]["active"] is True
    # No active branch in mirobod, must be active=False.
    assert by_code["mirobod"]["active"] is False
    # The Charlie branch was inactive, so sergeli is not active either.
    assert by_code["sergeli"]["active"] is False
