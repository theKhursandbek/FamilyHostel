"""
Payments & Salary models.

Database schema: README Section 14.4 (payments) & 14.7 (income_rules, salary_records).

Tables defined here:
    - payments
    - income_rules
    - salary_records

Business rules:
    - Payments must be idempotent (README 14.10)
    - Only PAID bookings count toward income
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Payment(models.Model):
    """
    Payment for a booking.

    Fields per README:
        - id, booking_id (FK), amount, payment_type,
          is_paid, paid_at, created_by (FK → administrators)
    """

    class PaymentType(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONLINE = "online", "Online"

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_type = models.CharField(
        max_length=10,
        choices=PaymentType.choices,
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.Administrator",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=["booking"], name="idx_payment_booking"),
            models.Index(fields=["is_paid"], name="idx_payment_is_paid"),
        ]

    def __str__(self):
        return f"Payment #{self.pk} — {self.amount} UZS ({self.payment_type})"


class IncomeRule(models.Model):
    """
    Income percentage rules per branch & shift.

    Fields per README:
        - id, branch_id (FK), shift_type, min_income,
          max_income, percent
    """

    class ShiftType(models.TextChoices):
        DAY = "day", "Day"
        NIGHT = "night", "Night"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="income_rules",
    )
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices)
    min_income = models.DecimalField(max_digits=14, decimal_places=2)
    max_income = models.DecimalField(max_digits=14, decimal_places=2)
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "income_rules"
        verbose_name = "Income Rule"
        verbose_name_plural = "Income Rules"

    def __str__(self):
        return f"Rule: {self.branch} {self.shift_type} ({self.percent}%)"


class SalaryRecord(models.Model):
    """
    Salary record for an account.

    Fields per README:
        - id, account_id (FK), amount, period_start,
          period_end, status, created_at
    """

    class SalaryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_records",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=SalaryStatus.choices,
        default=SalaryStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "salary_records"
        ordering = ["-created_at"]
        verbose_name = "Salary Record"
        verbose_name_plural = "Salary Records"

    def __str__(self):
        return f"Salary #{self.pk} — {self.account} ({self.status})"
