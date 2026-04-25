"""
Admin Panel models — Cash sessions, Room inspections & System settings.

Database schema: README Section 14.7.

Tables defined here:
    - cash_sessions
    - room_inspections      (Step 21.6)
    - room_inspection_images (Step 21.6)
    - system_settings
"""

from decimal import Decimal

from django.db import models

# Shared FK reference strings.
_ADMIN_FK = "accounts.Administrator"
_BRANCH_FK = "branches.Branch"


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
        _ADMIN_FK,
        on_delete=models.CASCADE,
        related_name="cash_sessions",
    )
    branch = models.ForeignKey(
        _BRANCH_FK,
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
        _ADMIN_FK,
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
    shift_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("100000"),
        help_text="Staff per-shift rate in UZS (used when salary mode = Shift-based).",
    )
    per_room_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("15000"),
        help_text="Staff per-cleaned-room rate in UZS (used when salary mode = Per-room).",
    )

    # ---- Per-role salary configuration (README §3.2/3.3/3.4) ------------
    director_fixed_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("2000000"),
        help_text="Director's fixed monthly salary in UZS (default 2,000,000).",
    )
    admin_shift_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("150000"),
        help_text="Administrator's per-shift rate in UZS.",
    )

    class Meta:
        db_table = "system_settings"
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Settings (mode={self.salary_mode}, cycle={self.salary_cycle})"


# ==============================================================================
# ROOM INSPECTION (Step 21.6)
# ==============================================================================


class RoomInspection(models.Model):
    """
    Room inspection performed by an administrator (Step 21.6).

    Typically done after guest checkout to verify room condition.

    Fields:
        - room, inspected_by (Administrator), status, notes,
          booking (optional link), branch, created_at
    """

    class InspectionStatus(models.TextChoices):
        CLEAN = "clean", "Clean"
        DAMAGED = "damaged", "Damaged"
        NEEDS_CLEANING = "needs_cleaning", "Needs Cleaning"

    room = models.ForeignKey(
        "branches.Room",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    branch = models.ForeignKey(
        _BRANCH_FK,
        on_delete=models.CASCADE,
        related_name="room_inspections",
    )
    inspected_by = models.ForeignKey(
        _ADMIN_FK,
        on_delete=models.CASCADE,
        related_name="room_inspections",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    status = models.CharField(
        max_length=20,
        choices=InspectionStatus.choices,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "room_inspections"
        ordering = ["-created_at"]
        verbose_name = "Room Inspection"
        verbose_name_plural = "Room Inspections"
        indexes = [
            models.Index(
                fields=["room", "created_at"],
                name="idx_inspection_room_date",
            ),
        ]

    def __str__(self):
        return (
            f"Inspection #{self.pk} — Room {self.room} "
            f"[{self.status}] by {self.inspected_by}"
        )


class RoomInspectionImage(models.Model):
    """
    Photo attached to a room inspection (Step 21.6).
    """

    inspection = models.ForeignKey(
        RoomInspection,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="inspection_images/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "room_inspection_images"
        verbose_name = "Room Inspection Image"
        verbose_name_plural = "Room Inspection Images"

    def __str__(self):
        return f"Image for Inspection #{self.inspection.pk}"
