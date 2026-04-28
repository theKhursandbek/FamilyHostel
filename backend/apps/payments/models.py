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

    Stripe fields (README Section 25.1 & 26.1):
        - payment_intent_id: Stripe PaymentIntent ID
        - stripe_event_id: Stripe event that confirmed the payment
    """

    class PaymentType(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONLINE = "online", "Online"

    class PaymentMethod(models.TextChoices):
        """How the cash actually moved (per April 2026 daily-ledger spec)."""
        CASH = "cash", "Cash"
        TERMINAL = "terminal", "Terminal (POS)"
        QR = "qr", "QR Code"
        CARD_TRANSFER = "card_transfer", "Transfer to Card"

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
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        help_text="How the money physically moved — cash / terminal / QR / card transfer.",
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

    # Stripe integration fields
    payment_intent_id = models.CharField(
        max_length=255,
        null=True,  # nullable unique: NULLs bypass unique constraint  # NOSONAR
        blank=True,
        unique=True,
        help_text="Stripe PaymentIntent ID (pi_...)",
    )
    stripe_event_id = models.CharField(
        max_length=255,
        null=True,  # optional Stripe field, consistent with payment_intent_id  # NOSONAR
        blank=True,
        help_text="Stripe event that confirmed this payment",
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
            models.Index(
                fields=["payment_intent_id"],
                name="idx_payment_intent_id",
            ),
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

    class SalaryKind(models.TextChoices):
        ADVANCE = "advance", "Advance"
        FINAL = "final", "Final"

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
    kind = models.CharField(
        max_length=10,
        choices=SalaryKind.choices,
        default=SalaryKind.FINAL,
        help_text=(
            "Lifecycle marker — 'advance' rows are paid days 15–20 of month M; "
            "'final' rows are paid days 1–5 of month M+1. "
            "See REFACTOR_PLAN_2026_04 §3.6."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "salary_records"
        ordering = ["-created_at"]
        verbose_name = "Salary Record"
        verbose_name_plural = "Salary Records"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "period_start", "period_end", "kind"],
                name="unique_salary_record_per_account_period_kind",
            ),
        ]

    def __str__(self):
        return f"Salary #{self.pk} — {self.account} ({self.status})"


class SalaryAuditLog(models.Model):
    """Audit trail for every mutation on a :class:`SalaryRecord`.

    README §3.1 requires SuperAdmin overrides to be logged. We extend that
    to every payroll mutation: lock (``calculated``), payout
    (``marked_paid``), manual amount edit (``overridden``).
    """

    class Action(models.TextChoices):
        CALCULATED = "calculated", "Calculated / Locked"
        MARKED_PAID = "marked_paid", "Marked Paid"
        OVERRIDDEN = "overridden", "Overridden"

    record = models.ForeignKey(
        SalaryRecord,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    before_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    after_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "salary_audit_logs"
        ordering = ["-created_at"]
        verbose_name = "Salary Audit Log"
        verbose_name_plural = "Salary Audit Logs"

    def __str__(self):
        return f"{self.action} on Salary #{self.record_id} by {self.actor}"


class ProcessedStripeEvent(models.Model):
    """
    Idempotency table for Stripe webhook events (README Section 25.1 & 26.1).

    Every processed Stripe event ID is stored here so that
    re-delivered webhooks are silently ignored.
    """

    event_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Stripe event ID (evt_...)",
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Stripe event type (e.g. payment_intent.succeeded)",
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "processed_stripe_events"
        verbose_name = "Processed Stripe Event"
        verbose_name_plural = "Processed Stripe Events"

    def __str__(self):
        return f"{self.event_type} — {self.event_id}"
