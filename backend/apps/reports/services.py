"""
Notification & Audit-Log services (README Section 14.9 & 23).

These are the *only* modules that touch the ``Notification`` and
``AuditLog`` tables.  Every other app calls these helpers.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.reports.models import AuditLog, Notification

logger = logging.getLogger(__name__)

__all__ = [
    "send_notification",
    "notify_role",
    "notify_roles",
    "log_action",
]


# ==============================================================================
# NOTIFICATION SERVICE
# ==============================================================================


def send_notification(
    *,
    account_id: int,
    notification_type: str,
    message: str,
) -> Notification:
    """
    Create an in-app notification for a single account.

    Args:
        account_id: Primary key of the target ``Account``.
        notification_type: One of ``Notification.NotificationType`` values.
        message: Human-readable message body.
    """
    notification = Notification.objects.create(
        account_id=account_id,
        type=notification_type,
        message=message,
    )
    logger.info(
        "Notification [%s] → account #%s: %s",
        notification_type,
        account_id,
        message[:120],
    )
    return notification


def notify_role(
    *,
    role: str,
    branch,
    notification_type: str,
    message: str,
) -> list[Notification]:
    """
    Create notifications for **all** accounts with *role* at *branch*.

    Supported roles: ``"staff"``, ``"administrator"``, ``"director"``.
    """
    from apps.accounts.models import Administrator, Director, Staff

    role_model_map = {
        "staff": Staff,
        "administrator": Administrator,
        "director": Director,
    }

    model_cls = role_model_map.get(role)
    if model_cls is None:
        logger.warning("notify_role called with unknown role: %s", role)
        return []

    account_ids = list(
        model_cls.objects.filter(branch=branch, is_active=True)
        .values_list("account_id", flat=True)
    )

    if not account_ids:
        return []

    notifications = Notification.objects.bulk_create([
        Notification(
            account_id=aid,
            type=notification_type,
            message=message,
        )
        for aid in account_ids
    ])

    logger.info(
        "Notification [%s] → %d %s(s) at branch %s",
        notification_type,
        len(notifications),
        role,
        branch,
    )
    return notifications


def notify_roles(
    *,
    roles: list[str],
    branch,
    notification_type: str,
    message: str,
) -> list[Notification]:
    """Convenience wrapper: notify *multiple* roles at once."""
    all_notifications: list[Notification] = []
    for role in roles:
        all_notifications.extend(
            notify_role(
                role=role,
                branch=branch,
                notification_type=notification_type,
                message=message,
            )
        )
    return all_notifications


# ==============================================================================
# AUDIT-LOG SERVICE
# ==============================================================================


def _get_primary_role(account) -> str:
    """Return the highest-priority role for audit tagging."""
    if account is None:
        return "system"
    roles = account.roles  # property defined on Account model
    return roles[0] if roles else "unknown"


def log_action(
    *,
    account=None,
    role: str = "",
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Record an audit-trail entry.

    If *role* is not provided it is derived from the account's
    highest-priority role (``superadmin > director > … > client``).
    """
    resolved_role = role or _get_primary_role(account)

    audit = AuditLog.objects.create(
        account=account,
        role=resolved_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before_data,
        after_data=after_data,
    )

    logger.info(
        "Audit: [%s] %s on %s#%s by %s",
        resolved_role,
        action,
        entity_type,
        entity_id,
        account,
    )
    return audit