"""
Booking model.

Database schema: README Section 14.4.

Tables defined here:
    - bookings

Booking statuses (README Section 19):
    pending → paid → completed
    pending → canceled

Business rules (README Section 4):
    - Only PAID bookings count as income
    - Canceled bookings excluded
    - Price stored at booking time
    - Discount max 50,000 UZS
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Booking(models.Model):
    """
    Room booking record.

    Fields per README:
        - id, client_id (FK), room_id (FK), branch_id (FK),
          check_in_date, check_out_date, price_at_booking,
          discount_amount, final_price, status, created_at
    """

    class BookingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELED = "canceled", "Canceled"

    class BookingSource(models.TextChoices):
        """Where the booking originated. Exactly two global channels."""
        MANUAL = "manual", "Manual"
        TELEGRAM = "telegram", "Telegram"

    client = models.ForeignKey(
        "accounts.Client",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    room = models.ForeignKey(
        "branches.Room",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    branch_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Per-branch booking sequence (Branch A #1, Branch B #1, ...). "
            "Allocated at creation; shown in the UI as '#<branch_number>'."
        ),
    )
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    price_at_booking = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("50000")),
        ],
        help_text="Max 50,000 UZS.",
    )
    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    source = models.CharField(
        max_length=20,
        choices=BookingSource.choices,
        default=BookingSource.MANUAL,
        help_text="Origin channel — walk-in, manual admin entry, or Telegram bot.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(check_out_date__gt=models.F("check_in_date")),
                name="booking_checkout_after_checkin",
            ),
            models.UniqueConstraint(
                fields=["branch", "branch_number"],
                name="uniq_booking_branch_number",
            ),
        ]
        indexes = [
            models.Index(
                fields=["room", "check_in_date", "check_out_date"],
                name="idx_booking_room_dates",
            ),
            models.Index(
                fields=["status"],
                name="idx_booking_status",
            ),
            # Plan §8 R10 — hot query paths
            models.Index(fields=["room", "status"], name="idx_booking_room_status"),
            models.Index(fields=["client", "status"], name="idx_booking_client_status"),
        ]

    def clean(self):
        super().clean()
        if self.check_in_date and self.check_out_date:
            if self.check_out_date <= self.check_in_date:
                raise ValidationError(
                    {"check_out_date": "Check-out date must be after check-in date."}
                )

    def __str__(self):
        return f"Booking #{self.pk} — Room {self.room} ({self.status})"


class BookingExtension(models.Model):
    """
    A single extension segment applied to a booking.

    Modelling extensions as their own rows lets us cancel *only the extended
    days* (Scenario A) while leaving the original paid stay untouched, and
    keeps a permanent trace for the booking card's nested **History** section.
    """

    class ExtensionStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="extensions",
    )
    previous_check_out_date = models.DateField(
        help_text="The booking's check-out date *before* this extension.",
    )
    new_check_out_date = models.DateField(
        help_text="The check-out date this extension pushed the booking to.",
    )
    additional_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    status = models.CharField(
        max_length=12,
        choices=ExtensionStatus.choices,
        default=ExtensionStatus.ACTIVE,
    )
    created_by = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_booking_extensions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "booking_extensions"
        ordering = ["-created_at"]
        verbose_name = "Booking Extension"
        verbose_name_plural = "Booking Extensions"
        indexes = [
            models.Index(
                fields=["booking", "status"],
                name="idx_bk_ext_booking_status",
            ),
        ]

    def __str__(self):
        return (
            f"Extension #{self.pk} — Booking #{self.booking_id} "
            f"({self.previous_check_out_date} → {self.new_check_out_date}, "
            f"{self.status})"
        )
