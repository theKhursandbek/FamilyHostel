"""
Unit tests — Telegram Bot notification service (Step 16).

All HTTP calls to the Telegram Bot API are mocked.

Tests cover:
    - send_telegram_message: success, retry on failure, no token skip
    - send_telegram_notification: with/without chat_id, missing account
    - Integration: send_notification fires Telegram
    - Integration: notify_role fires Telegram for each recipient
    - Signal: booking created triggers Telegram
    - Signal: payment created (paid) triggers Telegram
    - Signal: cleaning task assigned triggers Telegram
    - Late check-in triggers Telegram notification
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.reports.telegram_service import (
    send_telegram_message,
    send_telegram_notification,
)

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
)


# ===========================================================================
# send_telegram_message — low-level
# ===========================================================================


class TestSendTelegramMessage:
    """Tests for the low-level send_telegram_message function."""

    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="fake-token")
    def test_success_on_first_attempt(self, _mock_token, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_post.return_value = mock_resp

        result = send_telegram_message("12345", "Hello!")

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "12345"
        assert call_kwargs[1]["json"]["text"] == "Hello!"

    @patch("apps.reports.telegram_service.time.sleep")
    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="fake-token")
    def test_retries_on_failure_then_succeeds(self, _mock_token, mock_post, mock_sleep):
        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 500
        fail_resp.text = "Internal Server Error"

        ok_resp = MagicMock()
        ok_resp.ok = True

        mock_post.side_effect = [fail_resp, ok_resp]

        result = send_telegram_message("12345", "Retry test")

        assert result is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)  # first back-off

    @patch("apps.reports.telegram_service.time.sleep")
    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="fake-token")
    def test_fails_after_max_retries(self, _mock_token, mock_post, mock_sleep):
        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 502
        fail_resp.text = "Bad Gateway"

        mock_post.return_value = fail_resp

        result = send_telegram_message("12345", "Fail test")

        assert result is False
        assert mock_post.call_count == 3  # MAX_RETRIES
        assert mock_sleep.call_count == 2  # back-off between 1→2, 2→3

    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="")
    def test_skips_when_no_token(self, _mock_token, mock_post):
        result = send_telegram_message("12345", "No token")

        assert result is False
        mock_post.assert_not_called()

    @patch("apps.reports.telegram_service.time.sleep")
    @patch("apps.reports.telegram_service.requests.post")
    @patch("apps.reports.telegram_service._get_bot_token", return_value="fake-token")
    def test_handles_request_exception(self, _mock_token, mock_post, mock_sleep):
        import requests
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        result = send_telegram_message("12345", "Exception test")

        assert result is False
        assert mock_post.call_count == 3


# ===========================================================================
# send_telegram_notification — account-level
# ===========================================================================


@pytest.mark.django_db
class TestSendTelegramNotification:
    """Tests for the account-aware send_telegram_notification."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_sends_when_chat_id_present(self, mock_send):
        account = AccountFactory(telegram_chat_id="999888")

        result = send_telegram_notification(account.pk, "Test message")

        assert result is True
        mock_send.assert_called_once_with("999888", "Test message")

    @patch("apps.reports.telegram_service.send_telegram_message")
    def test_skips_when_no_chat_id(self, mock_send):
        account = AccountFactory(telegram_chat_id=None)

        result = send_telegram_notification(account.pk, "No chat")

        assert result is False
        mock_send.assert_not_called()

    @patch("apps.reports.telegram_service.send_telegram_message")
    def test_skips_when_account_missing(self, mock_send):
        result = send_telegram_notification(999999, "Missing account")

        assert result is False
        mock_send.assert_not_called()

    @patch("apps.reports.telegram_service.send_telegram_message")
    def test_skips_when_chat_id_empty_string(self, mock_send):
        account = AccountFactory(telegram_chat_id="")

        result = send_telegram_notification(account.pk, "Empty chat_id")

        assert result is False
        mock_send.assert_not_called()


# ===========================================================================
# Notification service integration
# ===========================================================================


@pytest.mark.django_db
class TestNotificationTelegramIntegration:
    """Verify that send_notification and notify_role trigger Telegram."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_send_notification_fires_telegram(self, mock_send):
        from apps.reports.services import send_notification

        account = AccountFactory(telegram_chat_id="tg_123")

        notification = send_notification(
            account_id=account.pk,
            notification_type="booking",
            message="Booking confirmed!",
        )

        assert notification.pk is not None
        mock_send.assert_called_once_with("tg_123", "Booking confirmed!")

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_notify_role_fires_telegram_per_account(self, mock_send):
        from apps.reports.services import notify_role

        branch = BranchFactory()
        admin1 = AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="admin_chat_1"),
        )
        admin2 = AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="admin_chat_2"),
        )

        notifications = notify_role(
            role="administrator",
            branch=branch,
            notification_type="payment",
            message="Payment received!",
        )

        assert len(notifications) == 2
        assert mock_send.call_count == 2
        chat_ids = {call.args[0] for call in mock_send.call_args_list}
        assert chat_ids == {"admin_chat_1", "admin_chat_2"}

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_notify_role_skips_accounts_without_chat_id(self, mock_send):
        from apps.reports.services import notify_role

        branch = BranchFactory()
        # admin with chat_id
        AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="has_chat"),
        )
        # admin without chat_id
        AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id=None),
        )

        notify_role(
            role="administrator",
            branch=branch,
            notification_type="system",
            message="Test",
        )

        # Telegram called for both, but only one actually sends
        # (the second will return False from send_telegram_notification)
        assert mock_send.call_count == 1


# ===========================================================================
# Signal-level integration tests
# ===========================================================================


@pytest.mark.django_db
class TestBookingSignalTelegram:
    """Booking creation triggers Telegram via signal."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_booking_created_notifies_branch_admins(self, mock_send):
        branch = BranchFactory()
        room_type = RoomTypeFactory()
        room = RoomFactory(branch=branch, room_type=room_type)
        client = ClientFactory()

        # Admin & director with chat IDs
        AdministratorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="adm_tg"),
        )
        DirectorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="dir_tg"),
        )

        # Creating a booking fires the signal
        BookingFactory(client=client, room=room, branch=branch)

        # Both admin and director should get Telegram messages
        assert mock_send.call_count == 2
        chat_ids = {call.args[0] for call in mock_send.call_args_list}
        assert chat_ids == {"adm_tg", "dir_tg"}


@pytest.mark.django_db
class TestPaymentSignalTelegram:
    """Payment creation (paid) triggers Telegram via signal."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_paid_payment_notifies_branch_roles(self, mock_send):
        from apps.payments.models import Payment

        branch = BranchFactory()
        room_type = RoomTypeFactory()
        room = RoomFactory(branch=branch, room_type=room_type)
        client = ClientFactory()
        booking = BookingFactory(client=client, room=room, branch=branch)

        # Reset mock after booking signal fires
        mock_send.reset_mock()

        DirectorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="dir_pay_tg"),
        )

        # Creating a paid payment triggers signal
        Payment.objects.create(
            booking=booking,
            amount=Decimal("500000"),
            payment_type="manual",
            is_paid=True,
        )

        assert mock_send.call_count >= 1
        chat_ids = {call.args[0] for call in mock_send.call_args_list}
        assert "dir_pay_tg" in chat_ids


@pytest.mark.django_db
class TestCleaningSignalTelegram:
    """Cleaning task assignment triggers Telegram via signal."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_task_assigned_notifies_staff(self, mock_send):
        from apps.cleaning.services import assign_task_to_staff, create_cleaning_task

        branch = BranchFactory()
        room_type = RoomTypeFactory()
        room = RoomFactory(branch=branch, room_type=room_type)
        staff = StaffFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="staff_tg"),
        )

        # Reset after any earlier signals
        mock_send.reset_mock()

        task = create_cleaning_task(room=room, branch=branch)

        mock_send.reset_mock()

        assign_task_to_staff(task=task, staff_profile=staff)

        # Signal fires → send_notification → Telegram
        assert mock_send.call_count >= 1
        chat_ids = {call.args[0] for call in mock_send.call_args_list}
        assert "staff_tg" in chat_ids


@pytest.mark.django_db
class TestLateAttendanceTelegram:
    """Late check-in triggers Telegram notification."""

    @patch("apps.reports.telegram_service.send_telegram_message", return_value=True)
    def test_late_checkin_notifies_directors_and_staff(self, mock_send):
        import datetime

        from django.utils import timezone

        from apps.staff.services import check_in

        branch = BranchFactory()

        # Director with Telegram
        DirectorFactory(
            branch=branch,
            account=AccountFactory(telegram_chat_id="dir_late_tg"),
        )

        # Staff member who will be late
        staff_account = AccountFactory(telegram_chat_id="staff_late_tg")
        StaffFactory(branch=branch, account=staff_account)

        # Use a date/time that guarantees lateness:
        # shift starts at 08:00, late threshold = 30min → check in at 09:00
        today = timezone.now().date()

        with patch("apps.staff.services.timezone.now") as mock_now:
            mock_now.return_value = timezone.make_aware(
                datetime.datetime.combine(today, datetime.time(9, 0)),
                timezone=timezone.get_current_timezone(),
            )

            check_in(
                account=staff_account,
                branch=branch,
                date=today,
                shift_type="day",
            )

        # Director gets late notification + staff gets personal late warning
        assert mock_send.call_count >= 2
        chat_ids = {call.args[0] for call in mock_send.call_args_list}
        assert "dir_late_tg" in chat_ids
        assert "staff_late_tg" in chat_ids
