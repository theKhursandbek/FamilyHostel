"""Phone-share handler — receives the contact and triggers /auth/telegram/phone/start/."""

from __future__ import annotations

import re

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..backend import BackendClient
from ..i18n import t
from .state import Step, get_lang, set_phone, set_step


_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


def _normalise(raw: str) -> str | None:
    cleaned = re.sub(r"[\s\-()]", "", (raw or "").strip())
    if not cleaned:
        return None
    if not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    return cleaned if _PHONE_RE.match(cleaned) else None


async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(context)
    contact = update.message.contact
    phone = _normalise(getattr(contact, "phone_number", "") if contact else "")

    if not phone:
        await update.message.reply_text(t("phone.invalid", lang))
        return

    set_phone(context, phone)
    backend = BackendClient(context.application.bot_data["config"])
    ok, _ = await backend.start_otp(phone)
    if not ok:
        await update.message.reply_text(
            t("error.generic", lang), reply_markup=ReplyKeyboardRemove()
        )
        return

    set_step(context, Step.AWAIT_OTP)
    await update.message.reply_text(
        t("phone.sent", lang), reply_markup=ReplyKeyboardRemove()
    )


def register_phone_handlers(app: Application) -> None:
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
