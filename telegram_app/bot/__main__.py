"""
Hotel onboarding bot (TELEGRAM_MINI_APP_PLAN.md §3.1, D19).

Conversation flow:
    /start
       └─ pick language (uz / ru / en)              [InlineKeyboard]
            └─ "Share your phone" prompt            [ReplyKeyboardMarkup w/ contact]
                 └─ POST /auth/telegram/phone/start  → SMS dispatched
                      └─ user types 6-digit code
                           └─ POST /auth/telegram/phone/verify → done
                                └─ "Open Mini App" button

Two bots in production: prod + staging, distinguished by the
``TELEGRAM_BOT_ENV`` env var (``prod`` or ``staging``). The bot picks its
token from ``TELEGRAM_BOT_TOKENS[env]`` and tags every backend request
with ``X-Telegram-Bot-Env`` so the backend logs / metrics can split.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .config import BotConfig
from .handlers.start import register_start_handlers
from .handlers.language import register_language_handlers
from .handlers.phone import register_phone_handlers
from .handlers.otp import register_otp_handlers


def _build_app(config: BotConfig) -> Any:
    # Imported lazily so unit tests can stub out python-telegram-bot.
    from telegram.ext import Application

    application = Application.builder().token(config.token).build()
    application.bot_data["config"] = config

    register_start_handlers(application)
    register_language_handlers(application)
    register_phone_handlers(application)
    register_otp_handlers(application)

    return application


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    config = BotConfig.from_env()
    app = _build_app(config)

    logging.getLogger("bot").info(
        "Starting FamilyHostel onboarding bot (env=%s, mini_app=%s)",
        config.env,
        config.mini_app_url,
    )
    app.run_polling()


if __name__ == "__main__":  # pragma: no cover
    main()
