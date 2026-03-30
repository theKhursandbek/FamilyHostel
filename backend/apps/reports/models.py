"""
Reports, Logs, Penalties & Notifications models.

Database schema: README Section 14.8 & 14.9.

Tables defined here:
    - monthly_reports  (14.8)
    - facility_logs    (14.8)
    - penalties        (14.9)
    - notifications    (14.9)
    - audit_logs       (14.9)
"""

from decimal import Decimal

from django.conf import settings
from django.db import models


class MonthlyReport(models.Model):
    """
    Monthly branch report prepared by Director.

    Fields per README:
        - id, branch_id (FK), month, year,
          created_by (FK → directors), summary_notes, created_at
    """

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="monthly_reports",
    )
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    created_by = models.ForeignKey(
        "accounts.Director",
        on_delete=models.CASCADE,
        related_name="monthly_reports",
    )
    summary_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monthly_reports"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "month", "year"],
                name="unique_branch_month_year",
            ),
        ]
        ordering = ["-year", "-month"]
        verbose_name = "Monthly Report"
        verbose_name_plural = "Monthly Reports"

    def __str__(self):
        return f"Report {self.month}/{self.year} — {self.branch}"


class FacilityLog(models.Model):
    """
    Facility issue log (gas, water, electricity, repair).

    Fields per README:
        - id, branch_id (FK), type, description, cost, created_at
    """

    class FacilityType(models.TextChoices):
        GAS = "gas", "Gas"
        WATER = "water", "Water"
        ELECTRICITY = "electricity", "Electricity"
        REPAIR = "repair", "Repair"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="facility_logs",
    )
    type = models.CharField(max_length=20, choices=FacilityType.choices)
    description = models.TextField()
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facility_logs"
        ordering = ["-created_at"]
        verbose_name = "Facility Log"
        verbose_name_plural = "Facility Logs"

    def __str__(self):
        return f"{self.type} — {self.branch} ({self.created_at:%Y-%m-%d})"


class Penalty(models.Model):
    """
    Penalty record for staff/admin.

    Fields per README:
        - id, account_id (FK), type, count, penalty_amount, created_at
    """

    class PenaltyType(models.TextChoices):
        LATE = "late", "Late"
        ABSENCE = "absence", "Absence"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="penalties",
    )
    type = models.CharField(max_length=10, choices=PenaltyType.choices)
    count = models.PositiveIntegerField(default=1)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "penalties"
        ordering = ["-created_at"]
        verbose_name = "Penalty"
        verbose_name_plural = "Penalties"

    def __str__(self):
        return f"Penalty: {self.type} — {self.account}"


class Notification(models.Model):
    """
    In-app / Telegram notification.

    Fields per README:
        - id, account_id (FK), type, message, is_read, created_at
    """

    class NotificationType(models.TextChoices):
        BOOKING = "booking", "Booking"
        PAYMENT = "payment", "Payment"
        CLEANING = "cleaning", "Cleaning"
        SHIFT = "shift", "Shift"
        PENALTY = "penalty", "Penalty"
        SYSTEM = "system", "System"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=50, choices=NotificationType.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notification: {self.type} → {self.account}"


class AuditLog(models.Model):
    """
    Audit trail for all important actions (README Section 23).

    Fields per README:
        - id, account_id (FK), role, action, entity_type,
          entity_id, before_data (JSONB), after_data (JSONB), created_at
    """

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    role = models.CharField(max_length=20)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.BigIntegerField(null=True, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"Audit: {self.action} on {self.entity_type}#{self.entity_id}"
