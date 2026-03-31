"""
Admin Panel models — Cash sessions & System settings.

Database schema: README Section 14.7.

Tables defined here:
    - cash_sessions
    - system_settings
"""

from decimal import Decimal

from django.db import models


class CashSession(models.Model):
    """
    Cash register session per admin shift.

    Fields per README:
        - id, admin_id (FK), branch_id (FK), shift_type,
          start_time, end_time, opening_balance, closing_balance,
          difference, note, handed_over_to (FK → administrators)
    """

    class ShiftType(models.TextChoices):
        DAY = "day", "Day"
        NIGHT = "night", "Night"

    admin = models.ForeignKey(
        "accounts.Administrator",
        on_delete=models.CASCADE,
        related_name="cash_sessions",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="cash_sessions",
    )
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2)
    closing_balance = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    difference = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    note = models.TextField(blank=True, default="")
    handed_over_to = models.ForeignKey(
        "accounts.Administrator",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_cash_sessions",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_sessions"
        ordering = ["-start_time"]
        verbose_name = "Cash Session"
        verbose_name_plural = "Cash Sessions"

    def __str__(self):
        return f"Cash Session #{self.pk} — {self.admin} ({self.shift_type})"


class SystemSettings(models.Model):
    """
    Global system settings (controlled by Super Admin).

    Fields per README:
        - id, salary_mode, salary_cycle, shift_rate
    """

    class SalaryMode(models.TextChoices):
        SHIFT = "shift", "Shift-based"
        PER_ROOM = "per_room", "Per-room-based"

    class SalaryCycle(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Bi-weekly"
        MONTHLY = "monthly", "Monthly"

    salary_mode = models.CharField(
        max_length=20,
        choices=SalaryMode.choices,
        default=SalaryMode.SHIFT,
    )
    salary_cycle = models.CharField(
        max_length=20,
        choices=SalaryCycle.choices,
        default=SalaryCycle.MONTHLY,
    )
    shift_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    per_room_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        db_table = "system_settings"
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Settings (mode={self.salary_mode}, cycle={self.salary_cycle})"
