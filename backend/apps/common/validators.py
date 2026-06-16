"""
Strict input validators shared by Mini App and admin endpoints.

Per TELEGRAM_MINI_APP_PLAN.md §11: every endpoint must validate every input.
This module gives serializers a uniform vocabulary so error shapes and
codes stay consistent across apps.

All helpers raise :class:`rest_framework.exceptions.ValidationError`
(``rest_framework.serializers.ValidationError`` is the same class) so they
plug into DRF serializer ``validate_<field>`` methods.
"""

from __future__ import annotations

import re
import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from rest_framework import serializers

# Allowed Mini App locales (TELEGRAM_MINI_APP_PLAN.md D9).
LANGUAGE_CHOICES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"

# Currency: UZS only (D17).
CURRENCY_UZS = "uzs"

# E.164-ish, biased toward +998 (Uzbekistan) but still permissive enough for
# the inevitable foreign Telegram contacts.
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")
_OTP_RE = re.compile(r"^\d{4,8}$")
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")


def _err(message: str, code: str | None = None):
    raise serializers.ValidationError(message, code=code)


# ---------------------------------------------------------------------------
# Numeric / textual primitives
# ---------------------------------------------------------------------------

def validate_int(value, *, field: str, min_value: int | None = None,
                 max_value: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        _err(f"{field}: must be an integer.", code="invalid")
    if min_value is not None and result < min_value:
        _err(f"{field}: must be ≥ {min_value}.", code="min_value")
    if max_value is not None and result > max_value:
        _err(f"{field}: must be ≤ {max_value}.", code="max_value")
    return result


def validate_decimal(value, *, field: str, max_digits: int = 14,
                     decimal_places: int = 2,
                     min_value: Decimal | None = None) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _err(f"{field}: must be a decimal number.", code="invalid")
    # Quantise to enforce decimal_places.
    quant = Decimal(10) ** -decimal_places
    result = result.quantize(quant)
    if min_value is not None and result < min_value:
        _err(f"{field}: must be ≥ {min_value}.", code="min_value")
    digits = result.as_tuple()
    if len(digits.digits) > max_digits:
        _err(f"{field}: max {max_digits} digits.", code="max_digits")
    return result


def validate_date(value, *, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        _err(f"{field}: must be ISO date (YYYY-MM-DD).", code="invalid")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _err(f"{field}: must be ISO date (YYYY-MM-DD).", code="invalid")


def validate_date_range(start, end, *, field_start="start", field_end="end",
                        min_nights: int = 1, max_nights: int = 365) -> tuple[date, date]:
    s = validate_date(start, field=field_start)
    e = validate_date(end, field=field_end)
    nights = (e - s).days
    if nights < min_nights:
        _err(
            f"{field_end}: must be at least {min_nights} night(s) after "
            f"{field_start}.",
            code="min_nights",
        )
    if nights > max_nights:
        _err(
            f"{field_end}: max stay is {max_nights} nights.",
            code="max_nights",
        )
    return s, e


def validate_uuid(value, *, field: str) -> _uuid.UUID:
    if isinstance(value, _uuid.UUID):
        return value
    if not isinstance(value, str) or not _UUID_RE.match(value):
        _err(f"{field}: must be a valid UUID.", code="invalid")
    try:
        return _uuid.UUID(value)
    except ValueError:
        _err(f"{field}: must be a valid UUID.", code="invalid")


# ---------------------------------------------------------------------------
# Domain-specific
# ---------------------------------------------------------------------------

def validate_phone(value, *, field: str = "phone") -> str:
    """Return a normalised E.164 phone number (always with leading ``+``)."""
    if not isinstance(value, str):
        _err(f"{field}: must be a string.", code="invalid")
    cleaned = re.sub(r"[\s\-()]", "", value.strip())
    if not _PHONE_RE.match(cleaned):
        _err(f"{field}: must be E.164 (e.g. +998901234567).", code="invalid_phone")
    return cleaned if cleaned.startswith("+") else f"+{cleaned}"


# ---------------------------------------------------------------------------
# Strict guest-identity validators (ported 1:1 from the Telegram Mini App,
# telegram_app/src/utils/validators.js, so the admin walk-in flow rejects
# exactly what the Mini App rejects). Plan §7.
# ---------------------------------------------------------------------------

# Uzbek phone: +998 followed by 9 digits (leading + optional on input).
_UZ_PHONE_RE = re.compile(r"^\+?998\d{9}$")
# Uzbek passport / ID: 2 uppercase letters + 7 digits, e.g. AB1234567.
_PASSPORT_RE = re.compile(r"^[A-Z]{2}\d{7}$")


def validate_person_name(value, *, field: str = "name",
                         min_len: int = 3, max_len: int = 20) -> str:
    """
    Validate a single name token (first OR last name).

    Mirrors the Mini App's ``NAME_RE = /^\\p{L}{3,20}$/u``: Unicode **letters
    only** — no spaces, digits, punctuation, hyphens or apostrophes — with a
    3–20 character length. Returns the stripped value.
    """
    if not isinstance(value, str):
        _err(f"{field}: must be a string.", code="invalid")
    cleaned = value.strip()
    if not cleaned.isalpha():
        _err(f"{field}: letters only, no spaces or symbols.", code="invalid_name")
    if not (min_len <= len(cleaned) <= max_len):
        _err(
            f"{field}: must be {min_len}–{max_len} letters.",
            code="invalid_name_length",
        )
    return cleaned


def validate_full_name(value, *, field: str = "full_name") -> str:
    """
    Validate a combined ``"First Last"`` full name.

    Splits on whitespace and validates each token with
    :func:`validate_person_name` (letters only, 3–20 chars). Requires 2–4
    tokens (first + last, optional middle names). Returns the re-joined,
    single-spaced name.
    """
    if not isinstance(value, str):
        _err(f"{field}: must be a string.", code="invalid")
    parts = value.split()
    if not (2 <= len(parts) <= 4):
        _err(
            f"{field}: enter a first and last name (letters only).",
            code="invalid_full_name",
        )
    cleaned = [validate_person_name(p, field=field) for p in parts]
    return " ".join(cleaned)


def validate_uz_phone(value, *, field: str = "phone") -> str:
    """
    Validate an Uzbek phone number, returning the normalised ``+998XXXXXXXXX``.

    Mirrors ``PHONE_RE = /^\\+998\\d{9}$/`` — exactly +998 plus 9 digits.
    Spaces, dashes and parentheses are stripped before matching.
    """
    if not isinstance(value, str):
        _err(f"{field}: must be a string.", code="invalid")
    cleaned = re.sub(r"[\s\-()]", "", value.strip())
    if not _UZ_PHONE_RE.match(cleaned):
        _err(
            f"{field}: must start with +998 and have 9 more digits.",
            code="invalid_phone",
        )
    return cleaned if cleaned.startswith("+") else f"+{cleaned}"


def validate_passport(value, *, field: str = "passport_number") -> str:
    """
    Validate an Uzbek passport/ID, returning the upper-cased value.

    Mirrors ``PASSPORT_RE = /^[A-Z]{2}\\d{7}$/`` — 2 letters + 7 digits.
    """
    if not isinstance(value, str):
        _err(f"{field}: must be a string.", code="invalid")
    cleaned = value.strip().upper()
    if not _PASSPORT_RE.match(cleaned):
        _err(
            f"{field}: must be 2 letters + 7 digits, e.g. AB1234567.",
            code="invalid_passport",
        )
    return cleaned


def validate_dob(value, *, field: str = "date_of_birth",
                 min_age: int = 16, max_age: int = 120) -> date:
    """
    Validate a date of birth: a real calendar date, not in the future, with
    age in ``[min_age, max_age]``. Mirrors the Mini App's ``validateDOB``
    (default minimum age **16**, maximum **120**).
    """
    d = validate_date(value, field=field)
    today = date.today()
    if d > today:
        _err(f"{field}: cannot be in the future.", code="future_dob")
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    if age < min_age:
        _err(
            f"{field}: guest must be at least {min_age} years old.",
            code="too_young",
        )
    if age > max_age:
        _err(
            f"{field}: please enter a valid date of birth.",
            code="too_old",
        )
    return d


def validate_otp(value, *, field: str = "code") -> str:
    if not isinstance(value, str) or not _OTP_RE.match(value):
        _err(f"{field}: must be 4-8 digits.", code="invalid_otp")
    return value


def validate_language(value, *, field: str = "language") -> str:
    if value in (None, ""):
        return DEFAULT_LANGUAGE
    if value not in LANGUAGE_CHOICES:
        _err(
            f"{field}: must be one of {', '.join(LANGUAGE_CHOICES)}.",
            code="invalid_choice",
        )
    return value


def validate_currency(value, *, field: str = "currency") -> str:
    if value is None:
        return CURRENCY_UZS
    if not isinstance(value, str) or value.lower() != CURRENCY_UZS:
        _err(f"{field}: only '{CURRENCY_UZS}' is supported.", code="invalid_choice")
    return CURRENCY_UZS


def validate_csv_int(value, *, field: str, max_items: int = 50) -> list[int]:
    if value in (None, ""):
        return []
    if not isinstance(value, str):
        _err(f"{field}: must be a comma-separated list of integers.", code="invalid")
    parts = [p for p in value.split(",") if p.strip()]
    if len(parts) > max_items:
        _err(f"{field}: max {max_items} items.", code="max_items")
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            _err(f"{field}: '{p}' is not an integer.", code="invalid")
    return out


def validate_csv_choice(value, *, field: str, choices: Iterable[str],
                        max_items: int = 20) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, str):
        _err(f"{field}: must be a comma-separated string.", code="invalid")
    parts = [p.strip() for p in value.split(",") if p.strip()]
    allowed = set(choices)
    if len(parts) > max_items:
        _err(f"{field}: max {max_items} items.", code="max_items")
    for p in parts:
        if p not in allowed:
            _err(
                f"{field}: '{p}' not in {sorted(allowed)}.",
                code="invalid_choice",
            )
    return parts


def validate_telegram_init_data(value, *, field: str = "init_data") -> str:
    if not isinstance(value, str) or len(value) < 10 or "hash=" not in value:
        _err(f"{field}: malformed Telegram initData.", code="invalid_init_data")
    if len(value) > 4096:
        _err(f"{field}: too large (max 4096 chars).", code="too_large")
    return value
