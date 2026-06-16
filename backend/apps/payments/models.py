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
    Monthly income percentage rules per branch.

    Fields:
        - id, branch_id (FK), min_income, max_income, percent
    """

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="income_rules",
    )
    min_income = models.DecimalField(max_digits=14, decimal_places=2)
    max_income = models.DecimalField(max_digits=14, decimal_places=2)
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "income_rules"
        verbose_name = "Income Rule"
        verbose_name_plural = "Income Rules"

    def __str__(self):
        return f"Rule: {self.branch} ≥{self.min_income} ({self.percent}%)"


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


# ===========================================================================
# Telegram Mini App — payment-first booking drafts (plan §4.2, D5).
# ===========================================================================

import uuid as _uuid

from django.utils import timezone


class _DraftStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"


class BookingDraft(models.Model):
    """A would-be booking awaiting Stripe ``payment_intent.succeeded``.

    Plan §4.2 / D5: clients never create a Booking directly. The Mini App
    creates a draft, pays it via Stripe Elements, and the webhook converts
    the draft into a real ``bookings.Booking`` row.
    """

    Status = _DraftStatus

    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    client = models.ForeignKey(
        "accounts.Client",
        on_delete=models.CASCADE,
        related_name="booking_drafts",
    )
    room = models.ForeignKey(
        "branches.Room", on_delete=models.PROTECT, related_name="+",
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="+",
    )
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="uzs")
    payment_intent_id = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING,
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="originating_draft",
    )
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField()  # created_at + 5 minutes (D12)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "booking_drafts"
        ordering = ["-created_at"]
        verbose_name = "Booking Draft"
        verbose_name_plural = "Booking Drafts"
        indexes = [
            models.Index(fields=["client", "status"], name="idx_draft_client_status"),
            models.Index(fields=["expires_at"], name="idx_draft_expires_at"),
        ]

    def __str__(self):
        return f"BookingDraft {self.id} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()


class ExtensionDraft(models.Model):
    """A would-be booking extension awaiting Stripe payment (plan §4.2)."""

    Status = _DraftStatus

    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="extension_drafts",
    )
    new_check_out_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="uzs")
    payment_intent_id = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=_DraftStatus.choices, default=_DraftStatus.PENDING,
    )
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extension_drafts"
        ordering = ["-created_at"]
        verbose_name = "Extension Draft"
        verbose_name_plural = "Extension Drafts"
        indexes = [
            models.Index(fields=["booking", "status"], name="idx_ext_booking_status"),
        ]

    def __str__(self):
        return f"ExtensionDraft {self.id} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

