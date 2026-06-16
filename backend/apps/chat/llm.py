"""
LLM proxy for the Mini App chat.

Features
--------
* OpenAI **or** Azure OpenAI — auto-selected via env:
    - ``AZURE_OPENAI_ENDPOINT`` + ``AZURE_OPENAI_KEY`` → Azure path
    - else ``OPENAI_API_KEY``                          → OpenAI path
    - else                                             → offline stub
* Function calling tools the assistant can invoke. Server **always** re-checks
  permissions before executing them so a malicious prompt cannot escalate.
    - ``search_rooms(branch?, max_price?, capacity?)``
    - ``get_my_bookings()``
    - ``cancel_booking(booking_id)``
* Suggestion chips returned alongside the reply (UI shortcuts).
* In-process rate limiting (5/min, 50/day) — DRF ScopedRateThrottle is the
  primary line of defence; this is belt-and-braces.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

PER_MINUTE = 5
PER_DAY = 50


class ChatRateLimited(Exception):
    """Raised when the caller exceeds the per-minute or per-day cap."""

    def __init__(self, scope: str):
        super().__init__(scope)
        self.scope = scope


def _check_rate(account_id: int) -> None:
    minute_key = f"chat:rl:m:{account_id}:{int(timezone.now().timestamp() // 60)}"
    day_key = f"chat:rl:d:{account_id}:{timezone.localdate().isoformat()}"
    minute_count = cache.get(minute_key, 0)
    if minute_count >= PER_MINUTE:
        raise ChatRateLimited("minute")
    day_count = cache.get(day_key, 0)
    if day_count >= PER_DAY:
        raise ChatRateLimited("day")
    cache.set(minute_key, minute_count + 1, timeout=70)
    cache.set(day_key, day_count + 1, timeout=int(timedelta(days=1).total_seconds()))


SYSTEM_PROMPT = (
    "You are the friendly virtual concierge of a small modern hotel. "
    "Answer questions about rooms, prices, check-in/out, amenities, payments, "
    "and our cancellation policy. Keep replies under 4 short sentences. "
    "When the user asks about availability, prices, or their bookings, USE "
    "the provided tools rather than guessing. Reply in the user's language."
)

DEFAULT_SUGGESTIONS = [
    "Show available rooms",
    "What's the check-in time?",
    "Cancel my booking",
]

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_rooms",
            "description": "Find rooms currently available for booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_id": {"type": "integer", "description": "Optional branch filter."},
                    "max_price": {"type": "number", "description": "Maximum price per night."},
                    "capacity": {"type": "integer", "description": "Minimum number of guests."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "Return the caller's recent and upcoming bookings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel one of the caller's own bookings by id.",
            "parameters": {
                "type": "object",
                "properties": {"booking_id": {"type": "integer"}},
                "required": ["booking_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations — every one re-checks the calling account.
# ---------------------------------------------------------------------------

def _tool_search_rooms(_account_id: int, args: dict) -> dict:
    from apps.rooms.models import Room
    qs = Room.objects.filter(status="available")
    if args.get("branch_id"):
        qs = qs.filter(branch_id=args["branch_id"])
    if args.get("max_price") is not None:
        qs = qs.filter(price_per_night__lte=args["max_price"])
    if args.get("capacity"):
        qs = qs.filter(capacity__gte=args["capacity"])
    rows = [
        {"id": r.id, "name": r.name, "price": float(r.price_per_night),
         "capacity": r.capacity, "branch_id": r.branch_id}
        for r in qs[:8]
    ]
    return {"rooms": rows}


def _tool_get_my_bookings(account_id: int, _args: dict) -> dict:
    from apps.bookings.models import Booking
    qs = (Booking.objects
          .filter(client__account_id=account_id)
          .order_by("-check_in")[:10])
    return {"bookings": [
        {"id": b.id, "room_id": b.room_id, "check_in": str(b.check_in),
         "check_out": str(b.check_out), "status": b.status}
        for b in qs
    ]}


def _tool_cancel_booking(account_id: int, args: dict) -> dict:
    from apps.bookings.models import Booking
    booking_id = args.get("booking_id")
    if not booking_id:
        return {"error": "booking_id is required"}
    try:
        b = Booking.objects.get(pk=booking_id, client__account_id=account_id)
    except Booking.DoesNotExist:
        return {"error": "Booking not found or not yours."}
    if b.status in ("cancelled", "checked_out"):
        return {"error": f"Booking already {b.status}."}
    b.status = "cancelled"
    b.save(update_fields=["status", "updated_at"])
    return {"ok": True, "booking_id": b.id, "status": b.status}


_DISPATCH = {
    "search_rooms": _tool_search_rooms,
    "get_my_bookings": _tool_get_my_bookings,
    "cancel_booking": _tool_cancel_booking,
}


def _run_tool(account_id: int, name: str, raw_args: str) -> str:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        args = {}
    handler = _DISPATCH.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return json.dumps(handler(account_id, args), default=str)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _make_client():
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
    azure_key = os.getenv("AZURE_OPENAI_KEY") or getattr(settings, "AZURE_OPENAI_KEY", "")
    if azure_endpoint and azure_key:
        from openai import AzureOpenAI
        return AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        ), getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None, ""
    from openai import OpenAI
    return OpenAI(api_key=api_key), getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_reply(account_id: int, messages: list[dict]) -> tuple[str, list[str]]:
    """Return ``(reply_text, suggestion_chips)`` for the given history."""

    _check_rate(account_id)

    client, model = _make_client()
    if not client:
        last = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        reply = (
            "Thanks for the message! I'm currently in offline-demo mode, but "
            "I heard: \u201c" + last[:140] + "\u201d. Reception will reply soon."
        )
        return reply, list(DEFAULT_SUGGESTIONS)

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    try:
        for _ in range(3):  # max 3 tool round-trips
            resp = client.chat.completions.create(
                model=model,
                messages=chat_messages,
                tools=TOOLS,
                temperature=0.4,
                max_tokens=400,
            )
            choice = resp.choices[0]
            msg = choice.message
            if not getattr(msg, "tool_calls", None):
                text = (msg.content or "").strip()
                return text, list(DEFAULT_SUGGESTIONS)

            chat_messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    } for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                result = _run_tool(account_id, tc.function.name, tc.function.arguments)
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        # Bailout if model keeps calling tools.
        return ("I tried a few lookups but didn't reach a final answer — could "
                "you rephrase, please?"), list(DEFAULT_SUGGESTIONS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chat LLM failure: %s", exc, exc_info=True)
        return (
            "Sorry \u2014 I couldn't reach my brain right now. Please try again "
            "in a moment, or message reception directly."
        ), list(DEFAULT_SUGGESTIONS)
