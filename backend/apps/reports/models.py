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

# String reference used by every FK that points at the branches app's
# Branch model. Centralised so refactors / app renames touch one place.
_BRANCH_MODEL = "branches.Branch"


class MonthlyReport(models.Model):
    """
    Monthly branch report prepared by Director.

    Fields per README:
        - id, branch_id (FK), month, year,
          created_by (FK → directors), summary_notes, created_at
    """

    branch = models.ForeignKey(
        _BRANCH_MODEL,
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
    Facility / operational expense log.

    Categories (April 2026 spreadsheet alignment):
        - products    — Продукты
        - detergents  — Моющие средства
        - telecom     — Телеком (интернет, связь)
        - repair      — Ремонт
        - utilities   — Коммуналка (gas / water / electricity)
        - other       — Прочие
    Optional shift_type tags the expense to a Day/Night cash session.
    """

    class FacilityType(models.TextChoices):
        PRODUCTS = "products", "Products"
        DETERGENTS = "detergents", "Detergents"
        TELECOM = "telecom", "Telecom"
        REPAIR = "repair", "Repair"
        UTILITIES = "utilities", "Utilities"
        OTHER = "other", "Other"

    class ShiftType(models.TextChoices):
        DAY = "day", "Day"
        NIGHT = "night", "Night"

    class LogStatus(models.TextChoices):
        """Expense-request lifecycle (REFACTOR_PLAN_2026_04 §7.1)."""

        PENDING = "pending", "Pending"
        APPROVED_CASH = "approved_cash", "Approved (cash)"
        APPROVED_CARD = "approved_card", "Approved (card)"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        RESOLVED = "resolved", "Resolved"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash (branch drawer)"
        CARD = "card", "Branch card (CEO swipe)"

    branch = models.ForeignKey(
        _BRANCH_MODEL,
        on_delete=models.CASCADE,
        related_name="facility_logs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_facility_logs",
        help_text="Director who filed this expense request.",
    )
    type = models.CharField(max_length=20, choices=FacilityType.choices)
    shift_type = models.CharField(
        max_length=10,
        choices=ShiftType.choices,
        null=True,
        blank=True,
    )
    description = models.TextField()
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField(
        max_length=15,
        choices=LogStatus.choices,
        default=LogStatus.PENDING,
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        null=True,
        blank=True,
        help_text="Set by CEO at approval time. Drives cash-vs-card subtotals.",
    )
    approved_by = models.ForeignKey(
        "accounts.SuperAdmin",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_facility_logs",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.TextField(blank=True, default="")
    rejected_by = models.ForeignKey(
        "accounts.SuperAdmin",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_facility_logs",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    over_limit_justified = models.BooleanField(default=False)
    over_limit_reason = models.TextField(blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    type = models.CharField(
        max_length=10,
        choices=PenaltyType.choices,
        null=True,
        blank=True,
        help_text=(
            "Optional categorisation (late/absence). Free-form penalties "
            "issued by Director/CEO leave this NULL — see "
            "REFACTOR_PLAN_2026_04 §2.1."
        ),
    )
    count = models.PositiveIntegerField(default=1)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_penalties",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class SalaryAdjustment(models.Model):
    """
    Free-form per-account monthly salary adjustment.

    Per REFACTOR_PLAN_2026_04 §3.7 / Q2 Option B (April 2026): replaces the
    per-month-row :class:`AdminMonthlyAdjustment`. Each row is **one
    explicit adjustment** entered by a Director or the CEO via the Salary
    page. Totals for a given (account, year, month) are aggregated on
    read.

    There is intentionally **no `advance` kind** here — advances are now
    auto-computed by the salary lifecycle (§3.4) and persisted as
    :class:`apps.payments.models.SalaryRecord` rows with
    ``kind='advance'``.
    """

    class Kind(models.TextChoices):
        PENALTY = "penalty", "Penalty (Жарима)"
        BONUS_PLUS = "bonus_plus", "Bonus + (Бонус +)"

    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_adjustments",
    )
    branch = models.ForeignKey(
        _BRANCH_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_adjustments",
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()  # 1–12
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
    )
    reason = models.TextField(
        blank=False,
        help_text="Required free-form explanation. See REFACTOR_PLAN_2026_04 §3.7.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_salary_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "salary_adjustments"
        ordering = ["-year", "-month", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "year", "month"]),
            models.Index(fields=["account", "year", "month"]),
        ]
        verbose_name = "Salary Adjustment"
        verbose_name_plural = "Salary Adjustments"

    def __str__(self):
        # ``account_id`` is a Django-generated FK accessor that Pyright's
        # default stubs don't see; the value is fine at runtime.
        return f"{self.kind} {self.amount} — acc#{self.account_id} {self.year}-{self.month:02d}"  # type: ignore[attr-defined]

