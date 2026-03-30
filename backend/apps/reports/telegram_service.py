"""
Telegram Bot notification service (README Section 26.4).

Sends messages via the Telegram Bot API ``sendMessage`` endpoint.
All Telegram logic is isolated here — views never call this directly.

Flow (README):
    Trigger event → create in-app notification → send via bot

Retry:
    If sending fails → retry up to 3 times with exponential back-off.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

__all__ = [
    "send_telegram_message",
    "send_telegram_notification",
]

# Telegram Bot API base URL
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1, 2, 4)  # exponential back-off


def _get_bot_token() -> str:
    """Return the configured bot token (or empty string if not set)."""
    return getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""


def send_telegram_message(
    chat_id: str | int,
    message: str,
    *,
    parse_mode: str = "HTML",
) -> bool:
    """
    Send a single message to a Telegram chat via the Bot API.

    Args:
        chat_id: Telegram chat ID of the recipient.
        message: Message body (HTML supported by default).
        parse_mode: Telegram parse mode (``HTML`` / ``Markdown``).

    Returns:
        ``True`` if the message was delivered, ``False`` otherwise.

    Retry:
        Up to 3 attempts with exponential back-off (1s, 2s, 4s).
        Every attempt (success or failure) is logged.
    """
    token = _get_bot_token()
    if not token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not configured — skipping message to %s.",
            chat_id,
        )
        return False

    url = TELEGRAM_API_URL.format(token=token)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.ok:
                logger.info(
                    "Telegram message sent to %s (attempt %d/%d).",
                    chat_id, attempt, MAX_RETRIES,
                )
                return True

            logger.warning(
                "Telegram API error for chat %s (attempt %d/%d): "
                "HTTP %s — %s",
                chat_id, attempt, MAX_RETRIES,
                response.status_code, response.text[:200],
            )
        except requests.RequestException as exc:
            logger.warning(
                "Telegram request failed for chat %s (attempt %d/%d): %s",
                chat_id, attempt, MAX_RETRIES, exc,
            )

        # Back-off before retry (skip sleep after last attempt)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

    logger.error(
        "Telegram message to %s FAILED after %d attempts.",
        chat_id, MAX_RETRIES,
    )
    return False


def send_telegram_notification(account_id: int, message: str) -> bool:
    """
    Send a Telegram notification to a single account (if they have a chat ID).

    This is the primary integration point called by the notification service.

    Args:
        account_id: PK of the ``Account``.
        message: Human-readable notification body.

    Returns:
        ``True`` if message was sent, ``False`` if skipped or failed.
    """
    from apps.accounts.models import Account

    try:
        account = Account.objects.only("telegram_chat_id").get(pk=account_id)
    except Account.DoesNotExist:
        logger.warning(
            "Telegram: account #%s does not exist — skipping.", account_id,
        )
        return False

    chat_id = account.telegram_chat_id
    if not chat_id:
        logger.debug(
            "Telegram: account #%s has no chat_id — skipping.", account_id,
        )
        return False

    return send_telegram_message(chat_id, message)
