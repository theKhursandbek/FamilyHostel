"""Shared per-user bot state."""

from __future__ import annotations

from enum import Enum


class Step(str, Enum):
    PICK_LANGUAGE = "pick_language"
    SHARE_PHONE = "share_phone"
    AWAIT_OTP = "await_otp"
    DONE = "done"


def get_lang(context) -> str:
    return (context.user_data or {}).get("lang", "uz")


def set_lang(context, lang: str) -> None:
    context.user_data["lang"] = lang


def get_phone(context) -> str | None:
    return (context.user_data or {}).get("phone")


def set_phone(context, phone: str) -> None:
    context.user_data["phone"] = phone


def get_step(context) -> Step:
    return Step((context.user_data or {}).get("step", Step.PICK_LANGUAGE))


def set_step(context, step: Step) -> None:
    context.user_data["step"] = step.value
