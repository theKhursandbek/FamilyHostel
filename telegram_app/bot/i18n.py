"""
Tiny i18n dictionary for the onboarding bot.

Three languages (uz default, then ru, en — TELEGRAM_MINI_APP_PLAN.md D9).
Keys are dotted; ``t("welcome.title", lang)`` returns the localised string,
falling back to the uz copy if a key is missing.
"""

from __future__ import annotations

from typing import Mapping

DEFAULT_LANG = "uz"
SUPPORTED = ("uz", "ru", "en")

MESSAGES: dict[str, Mapping[str, str]] = {
    "uz": {
        "welcome.title": "Assalomu alaykum!",
        "welcome.body": "Hotel onlayn xona bron qilish botiga xush kelibsiz.\n\nIltimos, tilni tanlang:",
        "lang.set": "Til \u201c{lang}\u201d sifatida saqlandi.",
        "phone.prompt": "Davom etish uchun telefon raqamingizni yuboring.",
        "phone.button": "\ud83d\udcf1 Raqamni ulashish",
        "phone.invalid": "Telefon raqami noto\u2018g\u2018ri. Qayta urining.",
        "phone.sent": "SMS yuborildi. Iltimos, 6 xonali kodni shu yerga yozing.",
        "otp.prompt": "Tasdiqlash kodini kiriting (6 raqam).",
        "otp.invalid": "Kod noto\u2018g\u2018ri. Qayta urining.",
        "otp.expired": "Kod muddati tugagan. /start dan boshlang.",
        "otp.success": "Tabriklaymiz! Telefon tasdiqlandi.",
        "open_app.button": "\ud83c\udfe8 Bron qilish",
        "open_app.body": "Endi xonalarni ko\u2018rib chiqing va bron qiling:",
        "error.generic": "Xatolik yuz berdi. Birozdan keyin urinib ko\u2018ring.",
    },
    "ru": {
        "welcome.title": "Добро пожаловать!",
        "welcome.body": "Это бот Hotel для бронирования номеров.\n\nВыберите язык:",
        "lang.set": "Язык установлен: «{lang}».",
        "phone.prompt": "Поделитесь своим номером телефона, чтобы продолжить.",
        "phone.button": "📱 Поделиться номером",
        "phone.invalid": "Неверный номер. Попробуйте ещё раз.",
        "phone.sent": "SMS отправлено. Введите 6-значный код здесь.",
        "otp.prompt": "Введите 6-значный код подтверждения.",
        "otp.invalid": "Код неверный. Попробуйте ещё раз.",
        "otp.expired": "Код истёк. Начните заново с /start.",
        "otp.success": "Готово! Телефон подтверждён.",
        "open_app.button": "🏨 Бронировать",
        "open_app.body": "Теперь откройте каталог и забронируйте номер:",
        "error.generic": "Произошла ошибка. Попробуйте чуть позже.",
    },
    "en": {
        "welcome.title": "Welcome!",
        "welcome.body": "This is the Hotel booking bot.\n\nPlease choose your language:",
        "lang.set": "Language set to \u201c{lang}\u201d.",
        "phone.prompt": "Share your phone number to continue.",
        "phone.button": "\ud83d\udcf1 Share phone",
        "phone.invalid": "Invalid phone number. Try again.",
        "phone.sent": "SMS sent. Type the 6-digit code here.",
        "otp.prompt": "Enter the 6-digit verification code.",
        "otp.invalid": "Wrong code. Try again.",
        "otp.expired": "Code expired. Start again with /start.",
        "otp.success": "Done! Your phone is verified.",
        "open_app.button": "\ud83c\udfe8 Open the booking app",
        "open_app.body": "Browse rooms and book now:",
        "error.generic": "Something went wrong. Try again shortly.",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **fmt) -> str:
    """Translate ``key`` into ``lang`` (fallback to uz)."""
    table = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    raw = table.get(key) or MESSAGES[DEFAULT_LANG].get(key) or key
    return raw.format(**fmt) if fmt else raw


def normalise_lang(code: str | None) -> str:
    if not code:
        return DEFAULT_LANG
    code = code.split("-")[0].lower()
    if code in SUPPORTED:
        return code
    if code in ("kk", "ky", "tg", "be"):
        return "ru"
    return DEFAULT_LANG
