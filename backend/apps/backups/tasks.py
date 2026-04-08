"""
Celery tasks for automated backup operations (Step 26).

Scheduled via CELERY_BEAT_SCHEDULE in settings:
    - backup_daily   : every day at 02:00 (server timezone)
    - backup_weekly   : every Sunday at 03:00
"""

import logging

from celery import shared_task

from apps.backups.services import cleanup_old_backups, create_backup

logger = logging.getLogger("backups")


@shared_task(
    name="backups.daily_backup",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def daily_backup(self):
    """Create a daily database backup and run retention cleanup."""
    try:
        filename = create_backup(backup_type="daily")
        deleted = cleanup_old_backups(backup_type="daily")
        logger.info(
            "Daily backup task complete: %s (cleaned up %d old backups)",
            filename,
            deleted,
        )
        return {"filename": filename, "deleted": deleted}
    except Exception as exc:
        logger.error("Daily backup failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="backups.weekly_backup",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def weekly_backup(self):
    """Create a weekly database backup and run retention cleanup."""
    try:
        filename = create_backup(backup_type="weekly")
        deleted = cleanup_old_backups(backup_type="weekly")
        logger.info(
            "Weekly backup task complete: %s (cleaned up %d old backups)",
            filename,
            deleted,
        )
        return {"filename": filename, "deleted": deleted}
    except Exception as exc:
        logger.error("Weekly backup failed: %s", exc)
        raise self.retry(exc=exc)
