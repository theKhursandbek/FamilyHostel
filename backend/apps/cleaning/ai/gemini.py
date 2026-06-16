"""
Gemini-powered cleanliness verification.

A single batched multimodal request judges all zone photos of one cleaning
task holistically and returns a structured verdict. The analyser ALWAYS fails
closed: any error, timeout, quota exhaustion or unparsable response yields a
``rejected`` verdict so a dirty room can never slip through on an AI outage.

Design notes:
    - One request per task (not per image) to respect the Gemini free-tier
      daily quota and to let the model reason about the room as a whole.
    - Absolute assessment ("is this clean and guest-ready?"), NOT similarity
      against the marketing/catalogue photos.
    - Structured JSON output via ``response_schema`` for deterministic parsing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger("cleaning.ai")


SYSTEM_INSTRUCTION = (
    "You are a strict hotel-room cleanliness inspector. You are given several "
    "photos of ONE room, each labelled with a zone (bed, bathroom, floor, "
    "trash). Decide whether the room is CLEAN and GUEST-READY.\n"
    "REJECT if you see any of: trash or litter, an unmade bed, stains, dirty "
    "or wet towels, a dirty toilet or sink, items left behind by a previous "
    "guest, or an un-emptied bin.\n"
    "Also REJECT as INVALID if a photo is: not a real hotel room, a photo of a "
    "screen or a printout, too blurry, or too dark to assess.\n"
    "Judge each zone, then give an overall verdict. Be concise and specific."
)

# Schema passed to Gemini so it returns clean, parseable JSON.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "overall": {"type": "string", "enum": ["approved", "rejected"]},
        "confidence": {"type": "number"},
        "summary": {"type": "string"},
        "zones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "zone": {"type": "string"},
                    "clean": {"type": "boolean"},
                    "issues": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["zone", "clean", "issues"],
            },
        },
    },
    "required": ["overall", "confidence", "summary", "zones"],
}


@dataclass
class AIVerdict:
    """Normalised result of an AI cleanliness check."""

    result: str  # "approved" | "rejected"
    summary: str
    zones: list[dict] = field(default_factory=list)
    confidence: float | None = None
    raw_response: str = ""
    failure_reason: str = ""
    model_version: str = ""

    @property
    def approved(self) -> bool:
        return self.result == "approved"


def _fail_closed(reason: str, *, model_version: str = "") -> AIVerdict:
    """Build a rejected verdict for an AI failure."""
    return AIVerdict(
        result="rejected",
        summary="Automatic verification could not confirm the room is clean. "
                "Please review or re-clean.",
        zones=[],
        confidence=None,
        raw_response="",
        failure_reason=reason,
        model_version=model_version,
    )


def _dev_stub(task) -> AIVerdict:
    """Deterministic local stub (only when CLEANING_AI_DEV_STUB=True).

    Approves when all required zones are present; rejects otherwise. Never
    used in production (the flag defaults to False).
    """
    from apps.cleaning.models import CleaningImage

    present = set(task.images.values_list("zone", flat=True))
    required = set(CleaningImage.REQUIRED_ZONES)
    if required.issubset(present):
        return AIVerdict(
            result="approved",
            summary=f"[dev-stub] All {len(required)} zones present — approved.",
            zones=[{"zone": z, "clean": True, "issues": []} for z in sorted(present)],
            confidence=1.0,
            model_version="dev-stub-v1",
        )
    missing = required - present
    return AIVerdict(
        result="rejected",
        summary=f"[dev-stub] Missing zones: {', '.join(sorted(missing))}.",
        zones=[],
        confidence=1.0,
        model_version="dev-stub-v1",
    )


def _parse_verdict(text: str, model_version: str) -> AIVerdict:
    """Parse Gemini's JSON text into an :class:`AIVerdict` (fail-closed)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Gemini returned unparsable JSON: %r", text[:200])
        return _fail_closed("unparsable_response", model_version=model_version)

    overall = str(data.get("overall", "")).lower()
    if overall not in ("approved", "rejected"):
        return _fail_closed("missing_verdict", model_version=model_version)

    confidence = data.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    return AIVerdict(
        result=overall,
        summary=str(data.get("summary", "")).strip(),
        zones=data.get("zones", []) or [],
        confidence=confidence,
        raw_response=text,
        failure_reason="",
        model_version=model_version,
    )


def analyze(task) -> AIVerdict:
    """Run cleanliness verification for a task's zone photos.

    Returns an :class:`AIVerdict`. Always fails closed (rejected) on any
    error when ``CLEANING_AI_FAIL_CLOSED`` is True (the default).
    """
    model_version = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    images = list(task.images.exclude(is_purged=True).order_by("zone"))
    if not images:
        return _fail_closed("no_images", model_version=model_version)

    # Local deterministic stub for development without a key.
    if getattr(settings, "CLEANING_AI_DEV_STUB", False):
        return _dev_stub(task)

    if not getattr(settings, "GEMINI_ENABLED", False) or not getattr(settings, "GEMINI_API_KEY", ""):
        logger.warning("Gemini disabled/unconfigured — failing closed for task %s.", task.pk)
        return _fail_closed("ai_disabled", model_version=model_version)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        parts = [f"Zones in order: {', '.join(i.zone for i in images)}."]
        contents: list = [SYSTEM_INSTRUCTION + "\n" + parts[0]]
        for img in images:
            img.image.open("rb")
            try:
                raw = img.image.read()
            finally:
                img.image.close()
            contents.append(
                types.Part.from_bytes(data=raw, mime_type="image/jpeg")
            )
            contents.append(f"(above photo = zone: {img.zone})")

        response = client.models.generate_content(
            model=model_version,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=800,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
        return _parse_verdict(response.text or "", model_version)

    except Exception as exc:  # noqa: BLE001 - any failure must fail closed
        logger.exception("Gemini analysis failed for task %s: %s", task.pk, exc)
        return _fail_closed(f"exception:{type(exc).__name__}", model_version=model_version)
