"""
Celery tasks for the Cleaning system.

Provides:
    - analyze_cleaning_images_task: Triggers AI validation for a cleaning task.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="cleaning.analyze_cleaning_images",
)
def analyze_cleaning_images_task(self, task_id: int) -> dict:
    """
    Celery task: Run AI analysis on cleaning images.

    1. Fetch the CleaningTask and its images.
    2. Call the AI service stub (``analyze_cleaning_images``).
    3. Store the result as an ``AIResult`` record.
    4. If rejected, mark the task as ``retry_required``.

    Returns:
        dict with ``task_id``, ``result``, ``feedback``.
    """
    from apps.cleaning.models import AIResult, CleaningTask
    from apps.cleaning.services import analyze_cleaning_images

    try:
        task = CleaningTask.objects.get(pk=task_id)
    except CleaningTask.DoesNotExist:
        logger.error("CleaningTask %d not found — skipping AI analysis.", task_id)
        return {"task_id": task_id, "result": "error", "feedback": "Task not found."}

    result, feedback = analyze_cleaning_images(task)

    # Store AIResult
    ai_result = AIResult.objects.create(
        task=task,
        result=result,
        feedback_text=feedback,
        ai_model_version="stub-v1.0",
    )

    # If rejected → mark task as retry_required
    if result == AIResult.Result.REJECTED:
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status", "updated_at"])
        logger.info(
            "CleaningTask %d AI-rejected — marked as retry_required.", task_id,
        )

    logger.info(
        "AI analysis for CleaningTask %d: result=%s", task_id, result,
    )

    return {
        "task_id": task_id,
        "ai_result_id": ai_result.pk,
        "result": result,
        "feedback": feedback,
    }
