"""
Tests for Step 21.4 — Real-time WebSocket system (Django Channels).

Covers:
    - Consumer authentication (accept/reject by role)
    - Group subscription (admin, director, super_admin groups)
    - Event dispatch utility (send_dashboard_event)
    - Signal integration (booking, payment, cleaning, attendance)
    - Message format verification
    - Configuration sanity checks
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import override_settings

from config.consumers import (
    AdminDashboardConsumer,
    DirectorDashboardConsumer,
    SuperAdminConsumer,
    WS_CLOSE_UNAUTHORIZED,
)
from config.ws_events import send_dashboard_event
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


# ==============================================================================
# HELPERS
# ==============================================================================


def _make_communicator(consumer_class, path="/ws/test/", user=None, query_string=""):
    """Build a WebsocketCommunicator with a pre-set user in scope."""
    communicator = WebsocketCommunicator(
        consumer_class.as_asgi(),
        path,
        subprotocols=[],
    )
    communicator.scope["user"] = user
    if query_string:
        communicator.scope["query_string"] = query_string.encode()
    return communicator


# ==============================================================================
# ADMIN CONSUMER TESTS
# ==============================================================================


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAdminDashboardConsumer:
    """Test AdminDashboardConsumer auth and group subscription."""

    async def test_admin_can_connect(self):
        admin = await database_sync_to_async(AdministratorFactory)()
        communicator = _make_communicator(
            AdminDashboardConsumer, "/ws/admin/", user=admin.account,
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_anonymous_rejected(self):
        from django.contrib.auth.models import AnonymousUser

        communicator = _make_communicator(
            AdminDashboardConsumer, "/ws/admin/", user=AnonymousUser(),
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_staff_rejected(self):
        staff = await database_sync_to_async(StaffFactory)()
        communicator = _make_communicator(
            AdminDashboardConsumer, "/ws/admin/", user=staff.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_client_rejected(self):
        client = await database_sync_to_async(ClientFactory)()
        communicator = _make_communicator(
            AdminDashboardConsumer, "/ws/admin/", user=client.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_receives_dashboard_event(self):
        admin = await database_sync_to_async(AdministratorFactory)()
        communicator = _make_communicator(
            AdminDashboardConsumer, "/ws/admin/", user=admin.account,
        )
        connected, _ = await communicator.connect()
        assert connected

        # Send event to the branch group.
        branch_id = await database_sync_to_async(
            lambda: admin.branch_id,
        )()
        channel_layer = get_channel_layer()
        await channel_layer.group_send(  # type: ignore[union-attr]
            f"branch_{branch_id}",
            {
                "type": "dashboard.event",
                "event_type": "booking.created",
                "data": {"booking_id": 1},
            },
        )

        response = await communicator.receive_json_from(timeout=2)
        assert response["type"] == "booking.created"
        assert response["data"]["booking_id"] == 1
        await communicator.disconnect()


# ==============================================================================
# DIRECTOR CONSUMER TESTS
# ==============================================================================


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestDirectorDashboardConsumer:
    """Test DirectorDashboardConsumer auth and group subscription."""

    async def test_director_can_connect(self):
        director = await database_sync_to_async(DirectorFactory)()
        communicator = _make_communicator(
            DirectorDashboardConsumer, "/ws/director/", user=director.account,
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_anonymous_rejected(self):
        from django.contrib.auth.models import AnonymousUser

        communicator = _make_communicator(
            DirectorDashboardConsumer, "/ws/director/", user=AnonymousUser(),
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_staff_rejected(self):
        staff = await database_sync_to_async(StaffFactory)()
        communicator = _make_communicator(
            DirectorDashboardConsumer, "/ws/director/", user=staff.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_superadmin_with_branch_id_can_connect(self):
        superadmin = await database_sync_to_async(SuperAdminFactory)()
        branch = await database_sync_to_async(BranchFactory)()
        branch_id = await database_sync_to_async(lambda: branch.pk)()
        communicator = _make_communicator(
            DirectorDashboardConsumer,
            "/ws/director/",
            user=superadmin.account,
            query_string=f"branch_id={branch_id}",
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_superadmin_without_branch_id_rejected(self):
        superadmin = await database_sync_to_async(SuperAdminFactory)()
        communicator = _make_communicator(
            DirectorDashboardConsumer, "/ws/director/", user=superadmin.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_receives_dashboard_event(self):
        director = await database_sync_to_async(DirectorFactory)()
        communicator = _make_communicator(
            DirectorDashboardConsumer, "/ws/director/", user=director.account,
        )
        connected, _ = await communicator.connect()
        assert connected

        branch_id = await database_sync_to_async(
            lambda: director.branch_id,
        )()
        channel_layer = get_channel_layer()
        await channel_layer.group_send(  # type: ignore[union-attr]
            f"branch_{branch_id}",
            {
                "type": "dashboard.event",
                "event_type": "payment.completed",
                "data": {"payment_id": 99, "amount": "150000"},
            },
        )

        response = await communicator.receive_json_from(timeout=2)
        assert response["type"] == "payment.completed"
        assert response["data"]["payment_id"] == 99
        await communicator.disconnect()


# ==============================================================================
# SUPER ADMIN CONSUMER TESTS
# ==============================================================================


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestSuperAdminConsumer:
    """Test SuperAdminConsumer auth and group subscription."""

    async def test_superadmin_can_connect(self):
        superadmin = await database_sync_to_async(SuperAdminFactory)()
        communicator = _make_communicator(
            SuperAdminConsumer, "/ws/super-admin/", user=superadmin.account,
        )
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_anonymous_rejected(self):
        from django.contrib.auth.models import AnonymousUser

        communicator = _make_communicator(
            SuperAdminConsumer, "/ws/super-admin/", user=AnonymousUser(),
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_director_rejected(self):
        director = await database_sync_to_async(DirectorFactory)()
        communicator = _make_communicator(
            SuperAdminConsumer, "/ws/super-admin/", user=director.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_admin_rejected(self):
        admin = await database_sync_to_async(AdministratorFactory)()
        communicator = _make_communicator(
            SuperAdminConsumer, "/ws/super-admin/", user=admin.account,
        )
        connected, code = await communicator.connect()
        assert connected is False

    async def test_receives_dashboard_event(self):
        superadmin = await database_sync_to_async(SuperAdminFactory)()
        communicator = _make_communicator(
            SuperAdminConsumer, "/ws/super-admin/", user=superadmin.account,
        )
        connected, _ = await communicator.connect()
        assert connected

        channel_layer = get_channel_layer()
        await channel_layer.group_send(  # type: ignore[union-attr]
            "super_admin",
            {
                "type": "dashboard.event",
                "event_type": "cleaning_task.updated",
                "data": {"task_id": 5, "status": "completed"},
            },
        )

        response = await communicator.receive_json_from(timeout=2)
        assert response["type"] == "cleaning_task.updated"
        assert response["data"]["task_id"] == 5
        await communicator.disconnect()


# ==============================================================================
# EVENT DISPATCH UTILITY TESTS
# ==============================================================================


@pytest.mark.django_db(transaction=True)
class TestSendDashboardEvent:
    """Test the send_dashboard_event helper."""

    def test_sends_to_super_admin_group(self):
        """Events always go to super_admin group."""
        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            send_dashboard_event(
                event_type="booking.created",
                data={"booking_id": 1},
            )

            # super_admin group should receive the event.
            calls = mock_layer.group_send.call_args_list
            assert len(calls) == 1
            group_name = calls[0][0][0]
            assert group_name == "super_admin"

    def test_sends_to_branch_and_super_admin(self):
        """When branch_id is provided, events go to both groups."""
        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            send_dashboard_event(
                event_type="payment.completed",
                data={"payment_id": 42},
                branch_id=7,
            )

            calls = mock_layer.group_send.call_args_list
            assert len(calls) == 2
            groups = {c[0][0] for c in calls}
            assert groups == {"branch_7", "super_admin"}

    def test_message_format(self):
        """Verify the channel message structure."""
        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            send_dashboard_event(
                event_type="attendance.updated",
                data={"attendance_id": 3},
                branch_id=1,
            )

            message = mock_layer.group_send.call_args_list[0][0][1]
            assert message["type"] == "dashboard.event"
            assert message["event_type"] == "attendance.updated"
            assert message["data"] == {"attendance_id": 3}

    def test_no_channel_layer_does_not_crash(self):
        """If CHANNEL_LAYERS not configured, function is a no-op."""
        with patch("config.ws_events.get_channel_layer", return_value=None):
            # Should not raise.
            send_dashboard_event(
                event_type="booking.created",
                data={"booking_id": 1},
            )

    def test_exception_does_not_propagate(self):
        """If channel layer raises, the exception is caught."""
        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock(side_effect=Exception("Redis down"))
            mock_gcl.return_value = mock_layer

            # Should not raise.
            send_dashboard_event(
                event_type="booking.created",
                data={"booking_id": 1},
                branch_id=1,
            )


# ==============================================================================
# SIGNAL INTEGRATION TESTS
# ==============================================================================


@pytest.mark.django_db
class TestSignalWebSocketIntegration:
    """Verify signals call send_dashboard_event."""

    def test_booking_signal_sends_event(self):
        """Creating a booking triggers a WS event."""
        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            booking = BookingFactory()

            calls = mock_layer.group_send.call_args_list
            # At least 2 calls: branch group + super_admin
            assert len(calls) >= 2
            messages = [c[0][1] for c in calls]
            event_types = [m["event_type"] for m in messages]
            assert "booking.created" in event_types

    def test_payment_signal_sends_event(self):
        """Creating a paid payment triggers a WS event."""
        from apps.payments.models import Payment

        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            booking = BookingFactory()
            # Reset mock to ignore booking signal calls.
            mock_layer.group_send.reset_mock()

            Payment.objects.create(
                booking=booking,
                amount=Decimal("100000"),
                payment_type="manual",
                is_paid=True,
            )

            calls = mock_layer.group_send.call_args_list
            assert len(calls) >= 2
            messages = [c[0][1] for c in calls]
            event_types = [m["event_type"] for m in messages]
            assert "payment.completed" in event_types

    def test_cleaning_task_signal_sends_event(self):
        """Creating a cleaning task triggers a WS event."""
        from apps.cleaning.models import CleaningTask

        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            branch = BranchFactory()
            rt = RoomTypeFactory()
            room = RoomFactory(branch=branch, room_type=rt)

            CleaningTask.objects.create(
                room=room,
                branch=branch,
                priority="normal",
            )

            calls = mock_layer.group_send.call_args_list
            assert len(calls) >= 2
            messages = [c[0][1] for c in calls]
            event_types = [m["event_type"] for m in messages]
            assert "cleaning_task.created" in event_types

    def test_attendance_signal_sends_event(self):
        """Creating an attendance record triggers a WS event."""
        from apps.staff.models import Attendance

        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            staff = StaffFactory()

            Attendance.objects.create(
                account=staff.account,
                branch=staff.branch,
                date=datetime.date.today(),
                shift_type="day",
                status="present",
            )

            calls = mock_layer.group_send.call_args_list
            assert len(calls) >= 2
            messages = [c[0][1] for c in calls]
            event_types = [m["event_type"] for m in messages]
            assert "attendance.created" in event_types

    def test_booking_update_sends_updated_event(self):
        """Updating a booking triggers a booking.updated WS event."""
        booking = BookingFactory()

        with patch("config.ws_events.get_channel_layer") as mock_gcl:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_gcl.return_value = mock_layer

            booking.status = "paid"
            booking.save()

            calls = mock_layer.group_send.call_args_list
            assert len(calls) >= 2
            messages = [c[0][1] for c in calls]
            event_types = [m["event_type"] for m in messages]
            assert "booking.updated" in event_types


# ==============================================================================
# CONFIGURATION TESTS
# ==============================================================================


class TestWebSocketConfiguration:
    """Verify settings and routing are correctly configured."""

    def test_channels_in_installed_apps(self):
        from django.conf import settings

        assert "channels" in settings.INSTALLED_APPS

    def test_asgi_application_set(self):
        from django.conf import settings

        assert settings.ASGI_APPLICATION == "config.asgi.application"

    def test_channel_layers_configured(self):
        from django.conf import settings

        assert "default" in settings.CHANNEL_LAYERS

    def test_routing_has_three_paths(self):
        from config.routing import websocket_urlpatterns

        assert len(websocket_urlpatterns) == 3

    def test_routing_paths(self):
        from config.routing import websocket_urlpatterns

        paths = [str(p.pattern) for p in websocket_urlpatterns]
        assert "ws/admin/" in paths
        assert "ws/director/" in paths
        assert "ws/super-admin/" in paths

    def test_ws_close_unauthorized_code(self):
        assert WS_CLOSE_UNAUTHORIZED == 4403
