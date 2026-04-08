"""
WebSocket consumers for real-time dashboard updates (Step 21.4).

Three consumers map to the role-based dashboard views:
    - ``AdminDashboardConsumer``    → group ``admin_{account_id}``
    - ``DirectorDashboardConsumer`` → group ``director_{branch_id}``
    - ``SuperAdminConsumer``        → group ``super_admin``

Authentication:
    Each consumer checks ``self.scope["user"]`` (populated by
    ``AuthMiddlewareStack``) and verifies the correct role.  Unauthorized
    connections are closed with code **4403**.

Message format (outbound):
    {
        "type": "<event_type>",
        "data": { ... }
    }
"""

from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)

# WebSocket close code for unauthorized connections.
WS_CLOSE_UNAUTHORIZED = 4403

# Default event type when none is specified.
DASHBOARD_UPDATE_EVENT = "dashboard.update"


# ==============================================================================
# Helpers
# ==============================================================================


@database_sync_to_async
def _has_role(user, role: str) -> bool:
    """Check whether *user* has a given role (DB hit wrapped for async)."""
    if not user or user.is_anonymous:
        return False
    if role == "administrator":
        return hasattr(user, "administrator_profile")
    if role == "director":
        return hasattr(user, "director_profile")
    if role == "superadmin":
        return hasattr(user, "superadmin_profile")
    return False


@database_sync_to_async
def _get_admin_branch_id(user) -> int | None:
    """Return the branch PK for an administrator, or None."""
    try:
        return user.administrator_profile.branch_id  # type: ignore[union-attr]
    except Exception:
        return None


@database_sync_to_async
def _get_director_branch_id(user) -> int | None:
    """Return the branch PK for a director, or None."""
    try:
        return user.director_profile.branch_id  # type: ignore[union-attr]
    except Exception:
        return None


# ==============================================================================
# Admin Dashboard Consumer
# ==============================================================================


class AdminDashboardConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for administrators.

    Group: ``admin_{account_id}``

    Receives branch-level events relevant to the admin's branch:
        - booking.created / booking.updated
        - payment.completed
        - cleaning_task.updated
        - attendance.updated
    """

    group_name: str = ""

    async def connect(self):
        user = self.scope.get("user")
        if not await _has_role(user, "administrator"):
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        assert user is not None  # guaranteed by _has_role check above
        self.group_name = f"admin_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Also join the branch group so branch-wide events arrive.
        branch_id = await _get_admin_branch_id(user)
        if branch_id:
            self.branch_group = f"branch_{branch_id}"
            await self.channel_layer.group_add(
                self.branch_group, self.channel_name,
            )

        await self.accept()
        logger.info("WS connected: admin group=%s", self.group_name)

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name,
            )
        if hasattr(self, "branch_group"):
            await self.channel_layer.group_discard(
                self.branch_group, self.channel_name,
            )

    # --- Event handlers (called by channel layer) ---

    async def dashboard_event(self, event):
        """Forward a dashboard event to the WebSocket client."""
        await self.send_json({
            "type": event.get("event_type", DASHBOARD_UPDATE_EVENT),
            "data": event.get("data", {}),
        })


# ==============================================================================
# Director Dashboard Consumer
# ==============================================================================


class DirectorDashboardConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for directors.

    Group: ``director_{branch_id}``

    Receives branch-level events:
        - booking.created / booking.updated
        - payment.completed
        - cleaning_task.updated
        - attendance.updated
    """

    group_name: str = ""

    async def connect(self):
        user = self.scope.get("user")

        is_director = await _has_role(user, "director")
        is_superadmin = await _has_role(user, "superadmin")

        if not (is_director or is_superadmin):
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        if is_director:
            branch_id = await _get_director_branch_id(user)
        else:
            # Super admin can pass branch_id as query param.
            branch_id = self._get_query_param("branch_id")

        if not branch_id:
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        self.group_name = f"director_{branch_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Also subscribe to the branch group.
        self.branch_group = f"branch_{branch_id}"
        await self.channel_layer.group_add(self.branch_group, self.channel_name)

        await self.accept()
        logger.info("WS connected: director group=%s", self.group_name)

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name,
            )
        if hasattr(self, "branch_group"):
            await self.channel_layer.group_discard(
                self.branch_group, self.channel_name,
            )

    def _get_query_param(self, key: str) -> int | None:
        """Extract an integer query-string param from the WebSocket scope."""
        query_string = self.scope.get("query_string", b"").decode()
        for part in query_string.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k == key:
                    try:
                        return int(v)
                    except (ValueError, TypeError):
                        return None
        return None

    # --- Event handlers ---

    async def dashboard_event(self, event):
        """Forward a dashboard event to the WebSocket client."""
        await self.send_json({
            "type": event.get("event_type", DASHBOARD_UPDATE_EVENT),
            "data": event.get("data", {}),
        })


# ==============================================================================
# Super Admin Consumer
# ==============================================================================


class SuperAdminConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for super admins.

    Group: ``super_admin``

    Receives system-wide events from all branches:
        - booking.created / booking.updated
        - payment.completed
        - cleaning_task.updated
        - attendance.updated
    """

    group_name: str = "super_admin"

    async def connect(self):
        user = self.scope.get("user")
        if not await _has_role(user, "superadmin"):
            await self.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("WS connected: super_admin group")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name, self.channel_name,
        )

    # --- Event handlers ---

    async def dashboard_event(self, event):
        """Forward a dashboard event to the WebSocket client."""
        await self.send_json({
            "type": event.get("event_type", DASHBOARD_UPDATE_EVENT),
            "data": event.get("data", {}),
        })
