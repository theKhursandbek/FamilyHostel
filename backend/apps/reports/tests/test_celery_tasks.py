"""
Unit tests — Celery tasks & integration (Step 17).

All tests run with CELERY_TASK_ALWAYS_EAGER = True (set in offline.py),
so tasks execute synchronously — no running worker needed.

Tests cover:
    - send_telegram_message_task: delegates to send_telegram_message
    - send_telegram_notification_task: delegates to send_telegram_notification
    - send_bulk_telegram_task: fans out to individual tasks
    - process_payment_event_task: processes Stripe event in background
    - Integration: services dispatch tasks via .delay()
    - Celery app autodiscover verifies tasks are registered
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.reports.tasks import (
    send_bulk_telegram_task,
    send_telegram_message_task,
    send_telegram_notification_task,
)

from conftest import (
    AccountFactory,
    AdministratorFactory,
    BookingFactory,
    BranchFactory,
    ClientFactory,
    RoomFactory,
    RoomTypeFactory,
)


# ===========================================================================
# send_telegram_message_task
# ===========================================================================


class TestSendTelegramMessageTask:
    """Tests for the low-level Celery task wrapper."""

    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="fake-tok")
    def test_task_calls_send_telegram_message(self, _tok, mock_post):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.ok = True
        mock_post.return_value = resp

        # CELERY_TASK_ALWAYS_EAGER → runs synchronously
        result = send_telegram_message_task.delay("12345", "Hello from task")  # type: ignore[attr-defined]
        assert result.get() is True
        mock_post.assert_called_once()

    @patch("apps.reports.telegram_service._get_bot_token", return_value="")
    def test_task_returns_false_when_no_token(self, _tok):
        result = send_telegram_message_task.delay("12345", "No token")  # type: ignore[attr-defined]
        assert result.get() is False


# ===========================================================================
# send_telegram_notification_task
# ===========================================================================


@pytest.mark.django_db
class TestSendTelegramNotificationTask:
    """Tests for the account-level Celery task."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_task_sends_to_account_with_chat_id(self, mock_send):
        account = AccountFactory(telegram_chat_id="tg_task_123")

        result = send_telegram_notification_task.delay(account.pk, "Task msg")  # type: ignore[attr-defined]
        assert result.get() is True
        mock_send.assert_called_once_with("tg_task_123", "Task msg")

    @patch("apps.reports.telegram_service.send_telegram_message")
    def test_task_skips_account_without_chat_id(self, mock_send):
        account = AccountFactory(telegram_chat_id=None)

        result = send_telegram_notification_task.delay(account.pk, "Skip")  # type: ignore[attr-defined]
        assert result.get() is False
        mock_send.assert_not_called()


# ===========================================================================
# send_bulk_telegram_task
# ===========================================================================


@pytest.mark.django_db
class TestSendBulkTelegramTask:
    """Tests for the fan-out bulk task."""

    @patch("apps.reports.tasks.send_telegram_notification_task.delay")
    def test_dispatches_individual_tasks(self, mock_delay):
        result = send_bulk_telegram_task.delay([1, 2, 3], "Bulk msg")  # type: ignore[attr-defined]
        assert result.get() == 3
        assert mock_delay.call_count == 3


# ===========================================================================
# process_payment_event_task
# ===========================================================================


@pytest.mark.django_db
class TestProcessPaymentEventTask:
    """Tests for the Stripe event processing task."""

    def test_processes_succeeded_event(self, booking):
        from apps.payments.models import Payment
        from apps.payments.tasks import process_payment_event_task

        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_celery_1",
        )

        event_data = {"object": {"id": "pi_celery_1"}}

        result = process_payment_event_task.delay(  # type: ignore[attr-defined]
            "evt_celery_1",
            "payment_intent.succeeded",
            event_data,
        )
        assert result.get() is True

        # Verify payment was marked as paid
        payment = Payment.objects.get(payment_intent_id="pi_celery_1")
        assert payment.is_paid is True

    def test_duplicate_event_returns_false(self, booking):
        from apps.payments.models import Payment
        from apps.payments.tasks import process_payment_event_task

        Payment.objects.create(
            booking=booking,
            amount=booking.final_price,
            payment_type="online",
            is_paid=False,
            payment_intent_id="pi_celery_2",
        )

        event_data = {"object": {"id": "pi_celery_2"}}

        first = process_payment_event_task.delay(  # type: ignore[attr-defined]
            "evt_celery_2", "payment_intent.succeeded", event_data,
        )
        second = process_payment_event_task.delay(  # type: ignore[attr-defined]
            "evt_celery_2", "payment_intent.succeeded", event_data,
        )
        assert first.get() is True
        assert second.get() is False


# ===========================================================================
# Services integration — tasks dispatched via .delay()
# ===========================================================================


@pytest.mark.django_db
class TestServicesDispatchTasks:
    """Verify that notification services dispatch Celery tasks."""

    @patch("apps.reports.tasks.send_telegram_notification_task.delay")
    def test_send_notification_dispatches_task(self, mock_delay):
        from apps.reports.services import send_notification

        account = AccountFactory()

        notification = send_notification(
            account_id=account.pk,
            notification_type="booking",
            message="Celery integration test",
        )

        assert notification.pk is not None
        mock_delay.assert_called_once_with(account.pk, "Celery integration test")

    @patch("apps.reports.tasks.send_bulk_telegram_task.delay")
    def test_notify_role_dispatches_bulk_task(self, mock_delay):
        from apps.reports.services import notify_role

        branch = BranchFactory()
        admin1 = AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="a1"),
        )
        admin2 = AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="a2"),
        )

        notifications = notify_role(
            role="administrator",
            branch=branch,
            notification_type="system",
            message="Bulk task test",
        )

        assert len(notifications) == 2
        mock_delay.assert_called_once()
        dispatched_ids = mock_delay.call_args[0][0]
        assert set(dispatched_ids) == {admin1.account_id, admin2.account_id}


# ===========================================================================
# Celery app discovery
# ===========================================================================


class TestCeleryAppDiscovery:
    """Verify Celery app is configured and discovers tasks."""

    def test_celery_app_loads(self):
        from config.celery import app
        assert app.main == "hostel"

    def test_tasks_are_registered(self):
        from config.celery import app
        # Force autodiscover
        app.autodiscover_tasks()
        registered = app.tasks.keys()
        assert "reports.send_telegram_message" in registered
        assert "reports.send_telegram_notification" in registered
        assert "reports.send_bulk_telegram" in registered
        assert "payments.process_payment_event" in registered
