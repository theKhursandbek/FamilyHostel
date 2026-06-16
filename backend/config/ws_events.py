"""
Helper functions for sending WebSocket events to dashboards.
"""

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

def send_dashboard_event(event_type: str, data: dict, branch_id: int | None = None) -> None:
    """
    Send a real-time event to the appropriate WebSocket groups.
    If branch_id is provided, it goes to 'branch_{branch_id}' and 'super_admin'.
    If no branch_id is provided, it goes only to 'super_admin'.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        message = {
            "type": "dashboard_event",  # Maps to consumers' `dashboard_event` method
            "event_type": event_type,
            "data": data,
        }

        # Send to superadmin group
        async_to_sync(channel_layer.group_send)("super_admin", message)

        # Send to specific branch group if applicable
        if branch_id:
            async_to_sync(channel_layer.group_send)(f"branch_{branch_id}", message)

    except Exception as e:
        logger.exception("Failed to send dashboard event: %s", e)
