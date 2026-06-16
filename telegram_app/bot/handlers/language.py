"""Language selection callback (``lang:<uz|ru|en>``)."""

from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..i18n import t
from .state import Step, set_lang, set_step


LANG_LABELS = {"uz": "O\u2018zbekcha", "ru": "Русский", "en": "English"}


async def on_lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, lang = query.data.split(":", 1)
    if lang not in LANG_LABELS:
        return
    set_lang(context, lang)
    set_step(context, Step.SHARE_PHONE)

    await query.edit_message_text(t("lang.set", lang, lang=LANG_LABELS[lang]))

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(t("phone.button", lang), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await query.message.chat.send_message(t("phone.prompt", lang), reply_markup=keyboard)


def register_language_handlers(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_lang_chosen, pattern=r"^lang:"))
