"""
Shift & Attendance models.

Database schema: README Section 14.6.

Tables defined here:
    - shift_assignments
    - attendance

Shift types: day (08:00–19:00/18:00), night (19:00–08:00/18:00–08:00)
Attendance statuses: present, late (>30 min), absent
"""

from django.conf import settings
from django.db import models


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
        "branches.Branch",
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
        "branches.Branch",
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
