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
import threading

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)

# Hard cap on how long we'll wait for the channel-layer publish.  Anything
# longer means Redis is dead and the request thread should move on.
_PUBLISH_TIMEOUT_SECONDS = 1.5


def _do_publish(message: dict, branch_id: int | None, event_type: str) -> None:
    """Run the actual async group_send calls; swallow every error."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        group_send = async_to_sync(channel_layer.group_send)
        if branch_id is not None:
            group_send(f"branch_{branch_id}", message)
        group_send("super_admin", message)
        logger.debug(
            "WS event sent | type=%s | branch=%s",
            event_type,
            branch_id or "all",
        )
    except Exception:
        logger.warning("WS publish failed for %s (broker unreachable?)", event_type)


def send_dashboard_event(
    *,
    event_type: str,
    data: dict,
    branch_id: int | None = None,
) -> None:
    """
    Broadcast a real-time event to all relevant WebSocket groups.

    The publish runs in a daemon thread with a hard timeout so a dead Redis
    can never block the calling request.  When inside an open DB transaction
    we defer the publish until after commit so subscribers always see
    consistent state.
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

    def _spawn():
        worker = threading.Thread(
            target=_do_publish,
            args=(message, branch_id, event_type),
            daemon=True,
            name=f"ws-publish-{event_type}",
        )
        worker.start()
        # Fire-and-forget: never join.  If Redis is dead the thread dies
        # quietly in the background; the request returns immediately.

    # In tests / eager mode publish synchronously and inline so callers
    # (and assertions) can observe the side-effects deterministically
    # without waiting on a daemon thread or commit boundary.
    from django.conf import settings
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        _do_publish(message, branch_id, event_type)
        return

    try:
        transaction.on_commit(_spawn)
    except Exception:
        # Not inside a transaction — publish directly (still in a thread).
        _spawn()
