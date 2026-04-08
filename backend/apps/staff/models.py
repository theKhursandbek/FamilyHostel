"""
Shift, Attendance & Day-Off Request models.

Database schema: README Section 14.6.

Tables defined here:
    - shift_assignments
    - attendance
    - day_off_requests (Step 21.5)

Shift types: day (08:00–19:00/18:00), night (19:00–08:00/18:00–08:00)
Attendance statuses: present, late (>30 min), absent
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# Shared FK reference string.
_BRANCH_FK = "branches.Branch"


class ShiftAssignment(models.Model):
    """
    Shift schedule assigned by Director.

    Fields per README:
        - id, account_id (FK), role, branch_id (FK),
          shift_type, date, assigned_by (FK → directors)
    """

    class Role(models.TextChoices):
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    class ShiftType(models.TextChoices):
        DAY = "day", "Day"
        NIGHT = "night", "Night"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shift_assignments",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    branch = models.ForeignKey(
        _BRANCH_FK,
        on_delete=models.CASCADE,
        related_name="shift_assignments",
    )
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices)
    date = models.DateField()
    assigned_by = models.ForeignKey(
        "accounts.Director",
        on_delete=models.CASCADE,
        related_name="assigned_shifts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shift_assignments"
        ordering = ["-date"]
        verbose_name = "Shift Assignment"
        verbose_name_plural = "Shift Assignments"
        # README 14.10: One admin per shift per branch
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "shift_type", "date", "role"],
                condition=models.Q(role="admin"),
                name="unique_admin_per_shift_per_branch",
            ),
        ]

    def __str__(self):
        return f"{self.account} — {self.shift_type} on {self.date}"


class Attendance(models.Model):
    """
    Attendance record (check-in / check-out).

    Fields per README:
        - id, account_id (FK), branch_id (FK), shift_type,
          check_in, check_out, status
    """

    class AttendanceStatus(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    branch = models.ForeignKey(
        _BRANCH_FK,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField(
        help_text="The calendar date this attendance record covers.",
    )
    shift_type = models.CharField(
        max_length=10,
        choices=ShiftAssignment.ShiftType.choices,
    )
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.ABSENT,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance"
        ordering = ["-date"]
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        indexes = [
            models.Index(fields=["account", "date"], name="idx_attendance_account_date"),
        ]

    def __str__(self):
        return f"{self.account} — {self.status} ({self.shift_type} on {self.date})"


class DayOffRequest(models.Model):
    """
    Day-off request submitted by staff / administrators (Step 21.5).

    Workflow:
        1. Staff creates a request (status=pending)
        2. Director approves or rejects
        3. Approved requests are considered in attendance logic

    Fields:
        - account: the requesting staff / admin
        - start_date, end_date: inclusive date range
        - reason: free-text justification
        - status: pending → approved | rejected
        - reviewed_by: director who reviewed
        - reviewed_at: timestamp of review
        - review_comment: optional comment from reviewer
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="day_off_requests",
    )
    branch = models.ForeignKey(
        _BRANCH_FK,
        on_delete=models.CASCADE,
        related_name="day_off_requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        "accounts.Director",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_day_off_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "day_off_requests"
        ordering = ["-created_at"]
        verbose_name = "Day Off Request"
        verbose_name_plural = "Day Off Requests"
        indexes = [
            models.Index(
                fields=["account", "status"],
                name="idx_dayoff_account_status",
            ),
        ]

    def __str__(self):
        return (
            f"DayOff #{self.pk}: {self.account} "
            f"({self.start_date} – {self.end_date}) [{self.status}]"
        )

    def clean(self):
        """Model-level validation: end_date >= start_date."""
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "End date cannot be before start date."},
            )
