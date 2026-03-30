"""
Root conftest — shared fixtures and factories for the entire test suite.

Uses factory_boy for model creation. All fixtures are function-scoped
(fresh per test) to ensure isolation.
"""

import datetime
from decimal import Decimal

import factory
import pytest
from django.utils import timezone
from rest_framework.test import APIClient


# ==============================================================================
# FACTORIES
# ==============================================================================


class AccountFactory(factory.django.DjangoModelFactory):
    """Create an Account (custom user model)."""

    class Meta:
        model = "accounts.Account"

    telegram_id = factory.Sequence(lambda n: 100_000_000 + n)
    phone = factory.LazyAttribute(lambda o: f"+99890{o.telegram_id % 10_000_000:07d}")
    is_active = True


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "branches.Branch"

    name = factory.Sequence(lambda n: f"Branch #{n}")
    location = factory.Faker("address")
    is_active = True


class RoomTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "branches.RoomType"

    name = factory.Sequence(lambda n: f"RoomType #{n}")


class RoomFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "branches.Room"

    branch = factory.SubFactory(BranchFactory)
    room_type = factory.SubFactory(RoomTypeFactory)
    room_number = factory.Sequence(lambda n: f"{n + 100}")
    status = "available"
    is_active = True


class ClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.Client"

    account = factory.SubFactory(AccountFactory)
    full_name = factory.Faker("name")


class StaffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.Staff"

    account = factory.SubFactory(AccountFactory)
    branch = factory.SubFactory(BranchFactory)
    full_name = factory.Faker("name")
    hire_date = factory.LazyFunction(lambda: datetime.date.today())
    is_active = True


class AdministratorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.Administrator"

    account = factory.SubFactory(AccountFactory)
    branch = factory.SubFactory(BranchFactory)
    full_name = factory.Faker("name")
    is_active = True


class DirectorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.Director"

    account = factory.SubFactory(AccountFactory)
    branch = factory.SubFactory(BranchFactory)
    full_name = factory.Faker("name")
    is_active = True


class SuperAdminFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.SuperAdmin"

    account = factory.SubFactory(AccountFactory)
    full_name = factory.Faker("name")


class BookingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "bookings.Booking"

    client = factory.SubFactory(ClientFactory)
    room = factory.SubFactory(RoomFactory)
    branch = factory.LazyAttribute(lambda o: o.room.branch)
    check_in_date = factory.LazyFunction(lambda: datetime.date.today())
    check_out_date = factory.LazyFunction(
        lambda: datetime.date.today() + datetime.timedelta(days=3),
    )
    price_at_booking = Decimal("500000")
    discount_amount = Decimal("0")
    final_price = Decimal("500000")
    status = "pending"


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def branch(db):
    return BranchFactory()


@pytest.fixture
def room_type(db):
    return RoomTypeFactory()


@pytest.fixture
def room(db, branch, room_type):
    return RoomFactory(branch=branch, room_type=room_type)


@pytest.fixture
def account(db):
    return AccountFactory()


@pytest.fixture
def client_profile(db, account):
    return ClientFactory(account=account)


@pytest.fixture
def staff_profile(db, branch):
    return StaffFactory(branch=branch)


@pytest.fixture
def admin_profile(db, branch):
    return AdministratorFactory(branch=branch)


@pytest.fixture
def director_profile(db, branch):
    return DirectorFactory(branch=branch)


@pytest.fixture
def superadmin_profile(db):
    return SuperAdminFactory()


@pytest.fixture
def admin_client(api_client, admin_profile):
    """APIClient authenticated as an administrator."""
    api_client.force_authenticate(user=admin_profile.account)
    return api_client


@pytest.fixture
def director_client(api_client, director_profile):
    """APIClient authenticated as a director."""
    api_client.force_authenticate(user=director_profile.account)
    return api_client


@pytest.fixture
def staff_client(api_client, staff_profile):
    """APIClient authenticated as staff."""
    api_client.force_authenticate(user=staff_profile.account)
    return api_client


@pytest.fixture
def superadmin_client(api_client, superadmin_profile):
    """APIClient authenticated as super admin."""
    api_client.force_authenticate(user=superadmin_profile.account)
    return api_client


@pytest.fixture
def booking(db, client_profile, room, branch):
    return BookingFactory(
        client=client_profile,
        room=room,
        branch=branch,
    )
