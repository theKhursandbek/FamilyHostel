"""
WebSocket event dispatch utility (Step 21.4).

Provides a synchronous helper ``send_dashboard_event()`` that broadcasts
events to channel-layer groups.  This is called from Django signals and
service functions (which are synchronous) and wraps the async channel
layer call via ``async_to_sync``.

Usage::

    from config.ws_events import send_dashboard_event

    send_dashboard_event(
        event_type="booking.created",
        data={"booking_id": 42, "status": "pending"},
        branch_id=1,
    )

Groups targeted per call:
    - ``branch_{branch_id}``  — admins & directors watching that branch
    - ``super_admin``         — super admins see everything
"""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def send_dashboard_event(
    *,
    event_type: str,
    data: dict,
    branch_id: int | None = None,
) -> None:
    """
    Broadcast a real-time event to all relevant WebSocket groups.

    Parameters
    ----------
    event_type : str
        The event identifier (e.g. ``"booking.created"``).
    data : dict
        Payload to include in the message (must be JSON-serializable).
    branch_id : int | None
        If provided, the event is also sent to ``branch_{branch_id}``.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.debug("No channel layer configured — skipping WS event %s", event_type)
        return

    message = {
        "type": "dashboard.event",
        "event_type": event_type,
        "data": data,
    }

    try:
        group_send = async_to_sync(channel_layer.group_send)

        # 1) Branch-level group (admins + directors of that branch receive it).
        if branch_id is not None:
            group_send(f"branch_{branch_id}", message)

        # 2) Super-admin group (always receives everything).
        group_send("super_admin", message)

        logger.debug(
            "WS event sent | type=%s | branch=%s",
            event_type,
            branch_id or "all",
        )
    except Exception:
        # Never let a WS failure break a Django request.
        logger.exception("Failed to send WS event %s", event_type)
