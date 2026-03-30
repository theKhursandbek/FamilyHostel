"""
Celery tasks — Reports / Telegram notifications (Step 17).

All heavy or I/O-bound operations that were previously called
synchronously are now dispatched as Celery tasks.

Tasks:
    - ``send_telegram_notification_task``  — send Telegram message to one account
    - ``send_telegram_message_task``       — low-level: send to a specific chat_id
    - ``send_bulk_telegram_task``          — fan-out Telegram to multiple accounts

Retry policy:
    - Up to 3 retries with exponential back-off (10s, 30s, 60s).
    - All failures are logged via the standard ``logging`` module.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="reports.send_telegram_message",
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    acks_late=True,
)
def send_telegram_message_task(
    self,
    chat_id: str | int,
    message: str,
    parse_mode: str = "HTML",
) -> bool:
    """
    Celery wrapper around ``send_telegram_message``.

    Retries up to 3 times with exponential back-off on any exception.
    """
    from apps.reports.telegram_service import send_telegram_message

    result = send_telegram_message(chat_id, message, parse_mode=parse_mode)
    if not result:
        logger.warning(
            "Celery task: Telegram message to %s returned False.", chat_id,
        )
    return result


@shared_task(
    bind=True,
    name="reports.send_telegram_notification",
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    acks_late=True,
)
def send_telegram_notification_task(
    self,
    account_id: int,
    message: str,
) -> bool:
    """
    Celery wrapper around ``send_telegram_notification``.

    Looks up the account's ``telegram_chat_id`` and sends the message
    via the Telegram Bot API.  Retries on failure.
    """
    from apps.reports.telegram_service import send_telegram_notification

    return send_telegram_notification(account_id, message)


@shared_task(
    bind=True,
    name="reports.send_bulk_telegram",
    max_retries=0,
    acks_late=True,
)
def send_bulk_telegram_task(
    self,
    account_ids: list[int],
    message: str,
) -> int:
    """
    Fan-out: dispatch individual ``send_telegram_notification_task``
    for each account.

    Returns the number of sub-tasks dispatched.
    """
    for aid in account_ids:
        send_telegram_notification_task.delay(aid, message)  # type: ignore[attr-defined]
    return len(account_ids)
