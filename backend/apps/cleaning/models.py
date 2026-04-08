"""
Cleaning System models.

Database schema: README Section 14.5.

Tables defined here:
    - cleaning_tasks
    - cleaning_images
    - ai_results

Task statuses (README Section 19):
    pending → in_progress → completed

Business rules (README Section 6 & 14.10):
    - Trigger: checkout
    - One active task per room (status != completed)
    - Staff self-assigns
    - AI validation required
    - Director override allowed (logged)
"""

from django.db import models


class CleaningTask(models.Model):
    """
    Cleaning task — triggered when guest checks out.

    Fields per README:
        - id, room_id (FK), branch_id (FK), status, priority,
          assigned_to (FK → staff), created_at, completed_at
    """

    class TaskStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        RETRY_REQUIRED = "retry_required", "Retry Required"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    room = models.ForeignKey(
        "branches.Room",
        on_delete=models.CASCADE,
        related_name="cleaning_tasks",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="cleaning_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    assigned_to = models.ForeignKey(
        "accounts.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cleaning_tasks",
    )
    retry_count = models.PositiveIntegerField(default=0)
    override_reason = models.TextField(blank=True, default="")
    overridden_by = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overridden_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cleaning_tasks"
        ordering = ["-created_at"]
        verbose_name = "Cleaning Task"
        verbose_name_plural = "Cleaning Tasks"
        constraints = [
            models.UniqueConstraint(
                fields=["room"],
                condition=~models.Q(status__in=["completed", "retry_required"]),
                name="unique_active_cleaning_task_per_room",
            ),
        ]
        indexes = [
            models.Index(fields=["room", "status"], name="idx_cleaning_room_status"),
        ]

    def __str__(self):
        return f"Task #{self.pk} — Room {self.room} ({self.status})"


class CleaningImage(models.Model):
    """
    Photo uploaded by staff for cleaning verification.

    Fields per README:
        - id, task_id (FK), image_url, uploaded_at
    """

    task = models.ForeignKey(
        CleaningTask,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="cleaning_images/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cleaning_images"
        verbose_name = "Cleaning Image"
        verbose_name_plural = "Cleaning Images"

    def __str__(self):
        return f"Image for Task #{self.task.pk} ({self.image.name})"


class AIResult(models.Model):
    """
    AI validation result for a cleaning task.

    Fields per README:
        - id, task_id (FK), result, feedback_text,
          ai_model_version, created_at
    """

    class Result(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    task = models.ForeignKey(
        CleaningTask,
        on_delete=models.CASCADE,
        related_name="ai_results",
    )
    result = models.CharField(max_length=10, choices=Result.choices)
    feedback_text = models.TextField(blank=True, default="")
    ai_model_version = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_results"
        ordering = ["-created_at"]
        verbose_name = "AI Result"
        verbose_name_plural = "AI Results"

    def __str__(self):
        return f"AI Result #{self.pk} — {self.result} for Task #{self.task.pk}"
