"""
Cleaning business logic (README Section 6 & 14.5).

Rules:
    - Task created when guest checks out (triggered by booking.services)
    - One active task per room  (status != completed)
    - Staff self-assigns (picks a pending task)
    - Task completed after AI approval OR Director override
    - AI rejection marks task as retry_required
    - Director can force-override at any time
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.branches.models import Room
from apps.cleaning.models import AIResult, CleaningTask
from apps.reports.services import log_action, notify_roles

logger = logging.getLogger(__name__)

__all__ = [
    "create_cleaning_task",
    "assign_task_to_staff",
    "director_assign_task",
    "complete_task",
    "retry_task",
    "override_task",
    "analyze_cleaning_images",
]


@transaction.atomic
def create_cleaning_task(
    *,
    room,
    branch,
    priority: str = "normal",
    assigned_to=None,
    performed_by=None,
) -> CleaningTask:
    """
    Create a cleaning task for a room that just had a guest checkout, OR
    one created manually from the admin UI.

    The DB ``UniqueConstraint`` (unique_active_cleaning_task_per_room) also
    prevents duplicates, but we check here for a friendlier error message.

    Args:
        room: Target room.
        branch: The branch the room belongs to.
        priority: ``low`` | ``normal`` | ``high``.
        assigned_to: Optional ``Staff`` instance. If provided, the task is
            opened directly in ``in_progress`` (skipping the self-pickup
            step). Auto-created tasks (post-checkout) leave this ``None``
            so any free staff member can pick them up.
        performed_by: Account performing the action (for audit).

    Returns:
        The created ``CleaningTask`` instance.

    Raises:
        ``ValidationError`` if the room already has an active task.
    """
    has_active = CleaningTask.objects.filter(
        room=room,
    ).exclude(
        status=CleaningTask.TaskStatus.COMPLETED,
    ).exists()

    if has_active:
        raise ValidationError(
            {"room": "This room already has an active cleaning task. "
                     "Complete it before creating another one for this room."}
        )

    # If pre-assigning a staff member, ensure they aren't already busy on
    # another active cleaning task — one room at a time.
    if assigned_to is not None:
        busy = (
            CleaningTask.objects
            .filter(assigned_to=assigned_to)
            .exclude(status=CleaningTask.TaskStatus.COMPLETED)
            .exists()
        )
        if busy:
            raise ValidationError(
                {"assigned_to": f"{getattr(assigned_to, 'full_name', 'This staff')} "
                                "already has an active cleaning task."}
            )

    initial_status = (
        CleaningTask.TaskStatus.IN_PROGRESS
        if assigned_to is not None
        else CleaningTask.TaskStatus.PENDING
    )
    task = CleaningTask.objects.create(
        room=room,
        branch=branch,
        status=initial_status,
        priority=priority,
        assigned_to=assigned_to,
    )

    # --- Audit + Notification ---
    log_action(
        account=performed_by,
        action="cleaning_task.created",
        entity_type="CleaningTask",
        entity_id=task.pk,
        after_data=_task_snapshot(task),
    )
    notify_roles(
        roles=["staff"],
        branch=branch,
        notification_type="cleaning",
        message=f"New cleaning task #{task.pk} for room {room} (priority: {priority}).",
    )

    return task


@transaction.atomic
def assign_task_to_staff(*, task: CleaningTask, staff_profile) -> CleaningTask:
    """
    Staff self-assigns a pending cleaning task.

    Rules:
        - Only ``pending`` tasks can be picked.
        - The staff member is set as ``assigned_to``.
        - Status transitions to ``in_progress``.
    """
    if task.status not in (
        CleaningTask.TaskStatus.PENDING,
        CleaningTask.TaskStatus.RETRY_REQUIRED,
    ):
        raise ValidationError(
            {"status": f"Cannot assign a task with status '{task.status}'."}
        )

    # One staff member may only have a single active task at a time.
    # They must finish their current cleaning before picking up another room.
    already_busy = (
        CleaningTask.objects
        .filter(assigned_to=staff_profile)
        .exclude(status=CleaningTask.TaskStatus.COMPLETED)
        .exclude(pk=task.pk)
        .exists()
    )
    if already_busy:
        raise ValidationError(
            {"detail": "You already have an active cleaning task. "
                       "Finish it before picking up another room."}
        )

    before = _task_snapshot(task)

    task.assigned_to = staff_profile
    task.status = CleaningTask.TaskStatus.IN_PROGRESS
    task.save(update_fields=["assigned_to", "status", "updated_at"])

    # --- Audit ---
    log_action(
        account=getattr(staff_profile, "account", None),
        action="cleaning_task.assigned",
        entity_type="CleaningTask",
        entity_id=task.pk,
        before_data=before,
        after_data=_task_snapshot(task),
    )

    return task


@transaction.atomic
def director_assign_task(
    *,
    task: CleaningTask,
    staff_profile,
    performed_by,
) -> CleaningTask:
    """
    Director assigns (or reassigns) any staff member to a cleaning task.

    Unlike ``assign_task_to_staff``, this:
        - Allows reassignment of in-progress tasks.
        - Moves pending tasks to in_progress automatically.
        - Cannot assign completed tasks.
    """
    if task.status == CleaningTask.TaskStatus.COMPLETED:
        raise ValidationError(
            {"status": "Cannot assign a completed task."},
        )

    # One staff member can only carry a single active task at a time.
    already_busy = (
        CleaningTask.objects
        .filter(assigned_to=staff_profile)
        .exclude(status=CleaningTask.TaskStatus.COMPLETED)
        .exclude(pk=task.pk)
        .exists()
    )
    if already_busy:
        raise ValidationError(
            {"detail": f"{getattr(staff_profile, 'full_name', 'This staff')} "
                       "already has an active cleaning task."}
        )

    before = _task_snapshot(task)

    task.assigned_to = staff_profile
    if task.status == CleaningTask.TaskStatus.PENDING:
        task.status = CleaningTask.TaskStatus.IN_PROGRESS
    task.save(update_fields=["assigned_to", "status", "updated_at"])

    log_action(
        account=performed_by,
        action="cleaning_task.director_assigned",
        entity_type="CleaningTask",
        entity_id=task.pk,
        before_data=before,
        after_data=_task_snapshot(task),
    )

    return task


@transaction.atomic
def complete_task(*, task: CleaningTask, performed_by=None) -> CleaningTask:
    """
    Mark a cleaning task as completed.

    Called after AI approval or Director override.
    Sets the room status back to ``available``.
    """
    if task.status not in (
        CleaningTask.TaskStatus.IN_PROGRESS,
        CleaningTask.TaskStatus.RETRY_REQUIRED,
    ):
        raise ValidationError(
            {"status": "Only in-progress or retry-required tasks can be completed."}
        )

    before = _task_snapshot(task)

    task.status = CleaningTask.TaskStatus.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "completed_at", "updated_at"])

    # Room is clean and ready
    Room.objects.filter(pk=task.room_id).update(status=Room.RoomStatus.AVAILABLE)

    # --- Audit ---
    log_action(
        account=performed_by,
        action="cleaning_task.completed",
        entity_type="CleaningTask",
        entity_id=task.pk,
        before_data=before,
        after_data=_task_snapshot(task),
    )

    return task


@transaction.atomic
def retry_task(*, task: CleaningTask, performed_by=None) -> CleaningTask:
    """
    Re-open a retry_required task so staff can re-clean and resubmit.

    Rules:
        - Only ``retry_required`` tasks can be retried.
        - Increments ``retry_count``.
        - Status transitions back to ``in_progress``.
    """
    if task.status != CleaningTask.TaskStatus.RETRY_REQUIRED:
        raise ValidationError(
            {"status": "Only tasks with status 'retry_required' can be retried."}
        )

    before = _task_snapshot(task)

    task.retry_count += 1
    task.status = CleaningTask.TaskStatus.IN_PROGRESS
    task.save(update_fields=["status", "retry_count", "updated_at"])

    # --- Audit ---
    log_action(
        account=performed_by,
        action="cleaning_task.retried",
        entity_type="CleaningTask",
        entity_id=task.pk,
        before_data=before,
        after_data=_task_snapshot(task),
    )

    return task


@transaction.atomic
def override_task(
    *,
    task: CleaningTask,
    performed_by,
    reason: str = "",
) -> CleaningTask:
    """
    Director force-approves a cleaning task, bypassing AI.

    Rules:
        - Task must not already be completed.
        - Records override_reason and overridden_by.
        - Sets status to completed.
        - Sets room back to available.
        - Logged in AuditLog.
    """
    if task.status == CleaningTask.TaskStatus.COMPLETED:
        raise ValidationError(
            {"status": "Task is already completed."}
        )

    before = _task_snapshot(task)

    task.status = CleaningTask.TaskStatus.COMPLETED
    task.completed_at = timezone.now()
    task.override_reason = reason
    task.overridden_by = performed_by
    task.save(update_fields=[
        "status", "completed_at", "override_reason",
        "overridden_by", "updated_at",
    ])

    # Room is clean and ready
    Room.objects.filter(pk=task.room_id).update(status=Room.RoomStatus.AVAILABLE)

    # --- Audit ---
    log_action(
        account=performed_by,
        action="cleaning_task.overridden",
        entity_type="CleaningTask",
        entity_id=task.pk,
        before_data=before,
        after_data=_task_snapshot(task),
    )

    logger.info(
        "Director override on CleaningTask %d by %s: %s",
        task.pk, performed_by, reason,
    )

    return task


def analyze_cleaning_images(task: CleaningTask) -> tuple[str, str]:
    """
    AI service stub — analyse images for a cleaning task.

    This is a placeholder that always returns ``approved``.
    In production, this would call an external AI API (e.g., Azure
    Computer Vision) with the uploaded images and return the result.

    Returns:
        Tuple of (result, feedback_text) where result is
        ``"approved"`` or ``"rejected"``.
    """
    image_count = task.images.count()
    if image_count == 0:
        return (
            AIResult.Result.REJECTED,
            "No images uploaded for verification.",
        )

    # --- STUB: always approve if images exist ---
    return (
        AIResult.Result.APPROVED,
        f"Cleaning verified — {image_count} image(s) analysed.",
    )


# ==============================================================================
# SNAPSHOT HELPER
# ==============================================================================


def _task_snapshot(task: CleaningTask) -> dict:
    """Return a JSON-serialisable dict of task state."""
    return {
        "id": task.pk,
        "status": task.status,
        "room_id": task.room_id,
        "branch_id": task.branch_id,
        "priority": task.priority,
        "assigned_to_id": task.assigned_to_id,
        "retry_count": task.retry_count,
        "override_reason": task.override_reason,
        "overridden_by_id": task.overridden_by_id,
        "completed_at": str(task.completed_at) if task.completed_at else None,
    }
