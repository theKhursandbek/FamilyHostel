"""
Client-facing Telegram notifications for booking lifecycle events.

All messages are sent in the client's preferred language (Account.language).
Uses the existing Celery task infrastructure from apps.reports.tasks so
the send is non-blocking and retried on failure — the booking transaction
is never rolled back because a notification failed.

Supported events:
    booking_confirmed  — booking created + payment cleared (status=paid)
    booking_canceled   — booking canceled by client or staff
    booking_completed  — guest checked out (status=completed)
    extension_confirmed — extension paid + dates extended
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message templates — one per event per language
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, str]] = {
    "booking_confirmed": {
        "uz": (
            "✅ <b>Bron tasdiqlandi!</b>\n"
            "Bron №{booking_id} — Xona {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "💰 Jami: {total} so'm"
        ),
        "ru": (
            "✅ <b>Бронирование подтверждено!</b>\n"
            "Бронь №{booking_id} — Номер {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "💰 Итого: {total} сум"
        ),
        "en": (
            "✅ <b>Booking confirmed!</b>\n"
            "Booking #{booking_id} — Room {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "💰 Total: {total} UZS"
        ),
    },
    "booking_canceled": {
        "uz": (
            "❌ <b>Bron bekor qilindi.</b>\n"
            "Bron №{booking_id} — Xona {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "⚠️ To'langan summa qaytarilmaydi."
        ),
        "ru": (
            "❌ <b>Бронирование отменено.</b>\n"
            "Бронь №{booking_id} — Номер {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "⚠️ Уплаченная сумма не возвращается."
        ),
        "en": (
            "❌ <b>Booking canceled.</b>\n"
            "Booking #{booking_id} — Room {room_number}\n"
            "📅 {check_in} → {check_out}\n"
            "⚠️ The amount paid is non-refundable."
        ),
    },
    "booking_canceled_pending": {
        # Separate template when status was pending (no money taken)
        "uz": (
            "❌ <b>Bron bekor qilindi.</b>\n"
            "Bron №{booking_id} — Xona {room_number}\n"
            "📅 {check_in} → {check_out}"
        ),
        "ru": (
            "❌ <b>Бронирование отменено.</b>\n"
            "Бронь №{booking_id} — Номер {room_number}\n"
            "📅 {check_in} → {check_out}"
        ),
        "en": (
            "❌ <b>Booking canceled.</b>\n"
            "Booking #{booking_id} — Room {room_number}\n"
            "📅 {check_in} → {check_out}"
        ),
    },
    "booking_completed": {
        "uz": (
            "🏁 <b>Chiqish rasmiylashtirildi.</b>\n"
            "Bron №{booking_id} — Xona {room_number}\n"
            "Xizmatimizdan foydalanganingiz uchun rahmat!"
        ),
        "ru": (
            "🏁 <b>Выезд оформлен.</b>\n"
            "Бронь №{booking_id} — Номер {room_number}\n"
            "Спасибо, что воспользовались нашим хостелом!"
        ),
        "en": (
            "🏁 <b>Checkout complete.</b>\n"
            "Booking #{booking_id} — Room {room_number}\n"
            "Thank you for staying with us!"
        ),
    },
    "extension_confirmed": {
        "uz": (
            "✅ <b>Muddati uzaytirildi!</b>\n"
            "Bron №{booking_id} — Xona {room_number}\n"
            "📅 Yangi chiqish sanasi: {new_check_out}\n"
            "💰 Qo'shimcha to'lov: {amount} so'm"
        ),
        "ru": (
            "✅ <b>Продление подтверждено!</b>\n"
            "Бронь №{booking_id} — Номер {room_number}\n"
            "📅 Новая дата выезда: {new_check_out}\n"
            "💰 Дополнительная оплата: {amount} сум"
        ),
        "en": (
            "✅ <b>Extension confirmed!</b>\n"
            "Booking #{booking_id} — Room {room_number}\n"
            "📅 New check-out date: {new_check_out}\n"
            "💰 Additional charge: {amount} UZS"
        ),
    },
}

_FALLBACK_LANG = "uz"
_SUPPORTED_LANGS = frozenset({"uz", "ru", "en"})


def _get_template(event: str, lang: str) -> str:
    """Return the message template for *event* in *lang*, falling back to uz."""
    lang = lang if lang in _SUPPORTED_LANGS else _FALLBACK_LANG
    templates = _TEMPLATES.get(event, {})
    return templates.get(lang) or templates.get(_FALLBACK_LANG, "")


def _format_date(d) -> str:
    """Format a date object as DD.MM.YYYY."""
    try:
        return d.strftime("%d.%m.%Y")
    except Exception:
        return str(d)


def _format_money(amount) -> str:
    """Format a Decimal/int as integer with thousands separator."""
    try:
        return f"{int(amount):,}".replace(",", " ")
    except Exception:
        return str(amount)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def notify_client_booking_confirmed(booking) -> None:
    """Send booking-confirmed notification to the client via Telegram."""
    _send(
        booking=booking,
        event="booking_confirmed",
        extra={"total": _format_money(booking.final_price)},
    )


def notify_client_booking_canceled(booking, *, was_paid: bool) -> None:
    """Send booking-canceled notification. Template differs if money was taken."""
    event = "booking_canceled" if was_paid else "booking_canceled_pending"
    _send(booking=booking, event=event)


def notify_client_booking_completed(booking) -> None:
    """Send checkout notification to the client."""
    _send(booking=booking, event="booking_completed")


def notify_client_extension_confirmed(booking, *, new_check_out, amount) -> None:
    """Send extension-confirmed notification to the client."""
    _send(
        booking=booking,
        event="extension_confirmed",
        extra={
            "new_check_out": _format_date(new_check_out),
            "amount": _format_money(amount),
        },
    )


# ---------------------------------------------------------------------------
# Internal sender
# ---------------------------------------------------------------------------

def _send(booking, *, event: str, extra: dict | None = None) -> None:
    """
    Build the localised message and dispatch it via Celery.

    Never raises — all errors are logged so the caller's transaction
    is never affected.
    """
    try:
        account = booking.client.account
        chat_id = account.telegram_chat_id
        if not chat_id:
            logger.debug(
                "Skipping Telegram notify for booking #%s — no chat_id on account #%s",
                booking.pk,
                account.pk,
            )
            return

        lang = (account.language or _FALLBACK_LANG).lower().split("-")[0]
        template = _get_template(event, lang)
        if not template:
            logger.warning("No template for event=%s lang=%s", event, lang)
            return

        kwargs = {
            "booking_id": booking.pk,
            "room_number": booking.room.room_number,
            "check_in": _format_date(booking.check_in_date),
            "check_out": _format_date(booking.check_out_date),
        }
        if extra:
            kwargs.update(extra)

        message = template.format(**kwargs)

        from apps.reports.tasks import send_telegram_message_task  # noqa: PLC0415
        send_telegram_message_task.delay(chat_id, message, "HTML")  # type: ignore[attr-defined]

        logger.info(
            "Queued Telegram notify event=%s booking=#%s chat_id=%s",
            event,
            booking.pk,
            chat_id,
        )

    except Exception:
        logger.exception(
            "Failed to queue Telegram notification for booking #%s (event=%s)",
            getattr(booking, "pk", "?"),
            event,
        )
