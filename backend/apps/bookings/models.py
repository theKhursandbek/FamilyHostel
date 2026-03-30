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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        constraints = [
            models.CheckConstraint(
                check=models.Q(check_out_date__gt=models.F("check_in_date")),
                name="booking_checkout_after_checkin",
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
