"""
Per-user WebSocket consumers for the Telegram Mini App.

Channels:
    /ws/client/  → ``client_{account_id}`` group  (booking/payment/chat updates)
    /ws/staff/   → ``staff_{account_id}``  group  (task verdicts, attendance,
                                                   salary, reminders)
"""
from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)

WS_CLOSE_UNAUTHORIZED = 4403
DEFAULT_EVENT = "user.update"


@database_sync_to_async
def _is_client(user) -> bool:
    if not user or user.is_anonymous:
        return False
    return hasattr(user, "client_profile")


@database_sync_to_async
def _is_staff(user) -> bool:
    if not user or user.is_anonymous:
        return False
    return (
        hasattr(user, "staff_profile")
        or hasattr(user, "administrator_profile")
        or hasattr(user, "director_profile")
        or hasattr(user, "superadmin_profile")
    )


class _PerUserConsumer(AsyncJsonWebsocketConsumer):
    role_name: str = ""
    group_prefix: str = ""

    async def connect(self):
        user = self.scope.get("user")
        check = _is_client if self.role_name == "client" else _is_staff
        if not await check(user):
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        self.group_name = f"{self.group_prefix}_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("WS connected: %s group=%s", self.role_name, self.group_name)

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name,
            )

    async def dashboard_event(self, event):
        await self.send_json({
            "type": event.get("event_type", DEFAULT_EVENT),
            "data": event.get("data", {}),
        })


class ClientConsumer(_PerUserConsumer):
    role_name = "client"
    group_prefix = "client"


class StaffConsumer(_PerUserConsumer):
    role_name = "staff"
    group_prefix = "staff"
