"""
Suspicious activity detection and auto-blocking service (Step 21.2).

This module provides a lightweight, DB-backed mechanism to:

1. **Track** suspicious events (failed logins, rate-limit hits, permission
   denials, abnormal behaviour) per IP address / user account.
2. **Block** an IP / account when thresholds are exceeded.
3. **Auto-recover** — blocks expire after ``BLOCK_DURATION`` (default 15 min).
4. **Manual reset** — a superadmin can clear all blocks for an IP / account.

The service is called from ``SecurityLoggingMiddleware`` and
``BlockedUserMiddleware`` — both in ``config/security/middleware.py``.

Design goals:
    - Minimal DB queries on the hot path (``is_blocked`` check).
    - Indexed lookups on ``(ip_address, activity_type)`` and ``is_blocked``.
    - No external dependencies (no Redis / ML).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

logger = logging.getLogger("security")

# ---------------------------------------------------------------------------
# Configurable thresholds & durations
# ---------------------------------------------------------------------------

# How many events of a given type before blocking?
ACTIVITY_THRESHOLDS: dict[str, int] = {
    "failed_login": 5,
    "rate_limit_exceeded": 10,
    "unauthorized_access": 8,
    "abnormal_behavior": 5,
}

# How long is the tracking window (events older than this are ignored)?
TRACKING_WINDOW = timedelta(minutes=5)

# How long a block lasts before auto-recovery.
BLOCK_DURATION = timedelta(minutes=15)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def track_suspicious_activity(
    ip_address: str,
    activity_type: str,
    account=None,
) -> bool:
    """
    Record one occurrence of a suspicious event and apply blocking if needed.

    Parameters
    ----------
    ip_address : str
        Client IP address.
    activity_type : str
        One of ``SuspiciousActivity.ActivityType`` values.
    account : Account | None
        The authenticated user, if any.

    Returns
    -------
    bool
        ``True`` if the IP/account was **blocked** as a result of this call.
    """
    # Lazy import to avoid circular dependency at module load time.
    from apps.accounts.models import SuspiciousActivity

    now = timezone.now()
    window_start = now - TRACKING_WINDOW

    # Upsert: get-or-create within the tracking window, then increment.
    record, created = SuspiciousActivity.objects.get_or_create(
        ip_address=ip_address,
        activity_type=activity_type,
        is_blocked=False,
        updated_at__gte=window_start,
        defaults={
            "account": account,
            "count": 1,
        },
    )

    if not created:
        # Atomic increment
        SuspiciousActivity.objects.filter(pk=record.pk).update(
            count=F("count") + 1,
            account=account or record.account,
        )
        record.refresh_from_db()

    threshold = ACTIVITY_THRESHOLDS.get(activity_type, 5)

    if record.count >= threshold:
        record.is_blocked = True
        record.blocked_until = now + BLOCK_DURATION
        record.save(update_fields=["is_blocked", "blocked_until", "updated_at"])

        logger.warning(
            "BLOCKED | ip=%s | type=%s | count=%d | until=%s | account=%s",
            ip_address,
            activity_type,
            record.count,
            record.blocked_until.isoformat(),
            account or "anonymous",
        )
        return True

    return False


def is_blocked(ip_address: str, account=None) -> bool:
    """
    Check whether *ip_address* or *account* is currently blocked.

    Expired blocks are cleaned up automatically (auto-recovery).

    Returns
    -------
    bool
        ``True`` if the caller should be rejected.
    """
    from apps.accounts.models import SuspiciousActivity

    now = timezone.now()

    # Auto-expire old blocks in one UPDATE.
    SuspiciousActivity.objects.filter(
        is_blocked=True,
        blocked_until__lte=now,
    ).update(is_blocked=False)

    # Check IP-based block.
    qs = SuspiciousActivity.objects.filter(
        is_blocked=True,
        blocked_until__gt=now,
    )

    if qs.filter(ip_address=ip_address).exists():
        return True

    # Check account-based block (only if authenticated).
    if account is not None and qs.filter(account=account).exists():
        return True

    return False


def reset_blocks(*, ip_address: str | None = None, account=None) -> int:
    """
    Manually clear all active blocks for a given IP and/or account.

    Returns the number of records that were unblocked.
    """
    from apps.accounts.models import SuspiciousActivity

    qs = SuspiciousActivity.objects.filter(is_blocked=True)

    if ip_address:
        qs = qs.filter(ip_address=ip_address)
    if account:
        qs = qs.filter(account=account)

    count = qs.update(is_blocked=False, blocked_until=None)
    if count:
        logger.info(
            "BLOCKS_RESET | ip=%s | account=%s | cleared=%d",
            ip_address or "*",
            account or "*",
            count,
        )
    return count


def get_block_status(ip_address: str) -> dict:
    """
    Return a summary of the current block status for an IP address.

    Useful for admin dashboards or API introspection endpoints.
    """
    from apps.accounts.models import SuspiciousActivity

    now = timezone.now()
    records = SuspiciousActivity.objects.filter(
        ip_address=ip_address,
        is_blocked=True,
        blocked_until__gt=now,
    )

    blocks = []
    for r in records:
        blocks.append({
            "activity_type": r.activity_type,
            "count": r.count,
            "blocked_until": r.blocked_until.isoformat() if r.blocked_until else None,
            "account_id": r.account_id,
        })

    return {
        "ip_address": ip_address,
        "is_blocked": len(blocks) > 0,
        "active_blocks": blocks,
    }
