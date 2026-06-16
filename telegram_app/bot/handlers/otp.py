"""OTP verification handler — accepts a 6-digit code, calls /verify, opens Mini App."""

from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..backend import BackendClient
from ..i18n import t
from .state import Step, get_lang, get_phone, get_step, set_step


_OTP_RE = re.compile(r"^\d{4,8}$")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if get_step(context) != Step.AWAIT_OTP:
        return  # ignore stray text in other steps
    lang = get_lang(context)
    phone = get_phone(context)
    code = (update.message.text or "").strip()
    if not _OTP_RE.match(code):
        await update.message.reply_text(t("otp.invalid", lang))
        return
    if not phone:
        await update.message.reply_text(t("otp.expired", lang))
        return

    backend = BackendClient(context.application.bot_data["config"])
    ok, payload = await backend.verify_otp(phone, code)
    if not ok:
        # 400 = wrong code, 429 = locked / too many; backend message is detail
        msg = (payload.get("error", {}) or {}).get("message") or payload.get("detail")
        await update.message.reply_text(msg or t("otp.invalid", lang))
        return

    set_step(context, Step.DONE)
    config = context.application.bot_data["config"]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            t("open_app.button", lang),
            web_app=WebAppInfo(url=f"{config.mini_app_url}&lang={lang}"),
        )
    ]])
    await update.message.reply_text(t("otp.success", lang))
    await update.message.reply_text(t("open_app.body", lang), reply_markup=keyboard)


def register_otp_handlers(app: Application) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
