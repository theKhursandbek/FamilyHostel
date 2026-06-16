"""
Celery tasks for the Cleaning system.

Provides:
    - analyze_cleaning_images_task: real Gemini cleanliness verification.
        Approved  -> auto-complete the task (room -> available).
        Rejected  -> mark retry_required + notify the assigned staff.
        Fail-closed on any AI error (never auto-approves).
    - purge_old_cleaning_images: delete photo files 30 days after task
        completion, keeping the AIResult verdict forever.
"""

from __future__ import annotations

import datetime
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("cleaning.ai")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="cleaning.analyze_cleaning_images",
)
def analyze_cleaning_images_task(self, task_id: int) -> dict:
    """Run AI verification for a cleaning task and act on the verdict.

    1. Fetch the task + its zone photos.
    2. Ask Gemini for a structured verdict (fail-closed on error).
    3. Persist an ``AIResult`` with the full breakdown.
    4. Approved -> auto-complete; Rejected -> retry_required + notify staff.
    5. Broadcast a WebSocket update so the UI can live-refresh.
    """
    from apps.cleaning.ai import gemini
    from apps.cleaning.models import AIResult, CleaningTask
    from apps.cleaning.services import complete_task

    try:
        task = CleaningTask.objects.select_related(
            "assigned_to", "room", "branch",
        ).get(pk=task_id)
    except CleaningTask.DoesNotExist:
        logger.error("CleaningTask %d not found — skipping AI analysis.", task_id)
        return {"task_id": task_id, "result": "error", "feedback": "Task not found."}

    # Only analyse tasks awaiting a verdict.
    if task.status not in (
        CleaningTask.TaskStatus.AI_CHECKING,
        CleaningTask.TaskStatus.IN_PROGRESS,
        CleaningTask.TaskStatus.RETRY_REQUIRED,
    ):
        logger.info("Task %d not awaiting AI (status=%s) — skipping.", task_id, task.status)
        return {"task_id": task_id, "result": "skipped", "feedback": task.status}

    verdict = gemini.analyze(task)

    ai_result = AIResult.objects.create(
        task=task,
        result=verdict.result,
        feedback_text=verdict.summary,
        zones=verdict.zones,
        confidence=verdict.confidence,
        raw_response=verdict.raw_response,
        failure_reason=verdict.failure_reason,
        ai_model_version=verdict.model_version or getattr(settings, "GEMINI_MODEL", ""),
    )

    if verdict.approved:
        # AI approved -> auto-complete (room -> available). performed_by=None
        # marks this as a system action in the audit log.
        try:
            complete_task(task=task, performed_by=None)
        except Exception:  # noqa: BLE001 - completion guard race; log + continue
            logger.exception("Auto-complete failed for task %d after AI approval.", task_id)
    else:
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status", "updated_at"])
        _notify_staff_rejected(task, verdict.summary)

    _broadcast_task_update(task)

    logger.info(
        "AI verification for task %d: result=%s (failure_reason=%s)",
        task_id, verdict.result, verdict.failure_reason or "-",
    )
    return {
        "task_id": task_id,
        "ai_result_id": ai_result.pk,
        "result": verdict.result,
        "feedback": verdict.summary,
    }


def _notify_staff_rejected(task, summary: str) -> None:
    """Notify the assigned staff that the AI rejected their submission."""
    try:
        from apps.reports.services import send_notification

        account_id = getattr(getattr(task.assigned_to, "account", None), "pk", None)
        if account_id:
            send_notification(
                account_id,
                "cleaning",
                f"Room {task.room} cleaning was rejected: {summary or 'please re-clean.'}",
            )
    except Exception:  # noqa: BLE001 - notification must never break the verdict
        logger.exception("Failed to notify staff of AI rejection (task %d).", task.pk)


def _broadcast_task_update(task) -> None:
    """Best-effort WebSocket nudge so dashboards live-refresh."""
    try:
        from config.ws_events import send_dashboard_event

        send_dashboard_event(
            "cleaning_task_updated",
            {"task_id": task.pk, "status": task.status},
            branch_id=task.branch_id,
        )
    except Exception:  # noqa: BLE001 - sockets are best-effort
        logger.debug("WS broadcast skipped for task %d.", task.pk)


@shared_task(name="cleaning.purge_old_cleaning_images")
def purge_old_cleaning_images() -> dict:
    """Delete cleaning photo files 30 days after task completion.

    The image rows + AIResult verdicts are KEPT for audit; only the binary
    files are removed and the row is flagged ``is_purged``. Idempotent.
    """
    from apps.cleaning.models import CleaningImage, CleaningTask

    retention_days = int(getattr(settings, "CLEANING_IMAGE_RETENTION_DAYS", 30))
    cutoff = timezone.now() - datetime.timedelta(days=retention_days)

    stale = CleaningImage.objects.filter(
        is_purged=False,
        task__status=CleaningTask.TaskStatus.COMPLETED,
        task__completed_at__lt=cutoff,
    ).select_related("task")

    purged = 0
    freed_bytes = 0
    for img in stale.iterator():
        freed_bytes += img.byte_size or 0
        try:
            if img.image:
                img.image.delete(save=False)
        except Exception:  # noqa: BLE001 - missing blob shouldn't block the flag
            logger.warning("Could not delete blob for CleaningImage %d.", img.pk)
        img.is_purged = True
        img.purged_at = timezone.now()
        img.save(update_fields=["is_purged", "purged_at"])
        purged += 1

    logger.info("Purged %d cleaning image(s), freed ~%d bytes.", purged, freed_bytes)
    return {"purged": purged, "freed_bytes": freed_bytes}
