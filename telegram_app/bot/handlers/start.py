"""``/start`` handler — greets the user and shows the language picker."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..i18n import MESSAGES, normalise_lang, t
from .state import Step, set_lang, set_step


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("O\u2018zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton("Русский", callback_data="lang:ru"),
        InlineKeyboardButton("English", callback_data="lang:en"),
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    detected = normalise_lang(getattr(user, "language_code", None))
    set_lang(context, detected)
    set_step(context, Step.PICK_LANGUAGE)

    body = f"<b>{t('welcome.title', detected)}</b>\n\n{t('welcome.body', detected)}"
    await update.message.reply_html(body, reply_markup=_language_keyboard())


def register_start_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
