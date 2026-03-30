"""
Cleaning business logic (README Section 6 & 14.5).

Rules:
    - Task created when guest checks out (triggered by booking.services)
    - One active task per room  (status != completed)
    - Staff self-assigns (picks a pending task)
    - Task completed after AI approval OR Director override
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.branches.models import Room
from apps.cleaning.models import CleaningTask

__all__ = [
    "create_cleaning_task",
    "assign_task_to_staff",
    "complete_task",
]


@transaction.atomic
def create_cleaning_task(*, room, branch, priority: str = "normal") -> CleaningTask:
    """
    Create a cleaning task for a room that just had a guest checkout.

    The DB ``UniqueConstraint`` (unique_active_cleaning_task_per_room) also
    prevents duplicates, but we check here for a friendlier error message.

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
            {"room": "This room already has an active cleaning task."}
        )

    task = CleaningTask.objects.create(
        room=room,
        branch=branch,
        status=CleaningTask.TaskStatus.PENDING,
        priority=priority,
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
    if task.status != CleaningTask.TaskStatus.PENDING:
        raise ValidationError(
            {"status": f"Cannot assign a task with status '{task.status}'."}
        )

    task.assigned_to = staff_profile
    task.status = CleaningTask.TaskStatus.IN_PROGRESS
    task.save(update_fields=["assigned_to", "status", "updated_at"])

    return task


@transaction.atomic
def complete_task(*, task: CleaningTask) -> CleaningTask:
    """
    Mark a cleaning task as completed.

    Called after AI approval or Director override.
    Sets the room status back to ``available``.
    """
    if task.status != CleaningTask.TaskStatus.IN_PROGRESS:
        raise ValidationError(
            {"status": "Only in-progress tasks can be completed."}
        )

    task.status = CleaningTask.TaskStatus.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "completed_at", "updated_at"])

    # Room is clean and ready
    Room.objects.filter(pk=task.room_id).update(status=Room.RoomStatus.AVAILABLE)

    return task
