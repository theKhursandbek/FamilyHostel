"""
Payment business logic (README Section 14.4 & 14.10).

Rules:
    - Mark booking as ``paid`` when payment is successful
    - Idempotency: prevent double payment for the same booking
    - Only ``pending`` bookings can be paid
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.reports.services import log_action, notify_roles

__all__ = [
    "record_payment",
]


@transaction.atomic
def record_payment(
    *,
    booking: Booking,
    amount,
    payment_type: str,
    created_by=None,
) -> Payment:
    """
    Record a payment and transition the booking to ``paid``.

    Idempotency guard:
        - If the booking already has a successful payment, raise an error.

    Steps:
        1. Check the booking is still ``pending``
        2. Ensure no existing successful payment (idempotency)
        3. Create the Payment record
        4. Mark the payment as paid
        5. Transition booking status to ``paid``

    Returns:
        The created ``Payment`` instance.

    Raises:
        ``ValidationError`` on any rule violation.
    """
    # 1. Status check
    if booking.status != Booking.BookingStatus.PENDING:
        raise ValidationError(
            {"booking": f"Cannot pay for a booking with status '{booking.status}'."}
        )

    # 2. Idempotency guard
    if Payment.objects.filter(booking=booking, is_paid=True).exists():
        raise ValidationError(
            {"booking": "This booking has already been paid."}
        )

    # 3-4. Create and mark paid
    now = timezone.now()
    payment = Payment.objects.create(
        booking=booking,
        amount=amount,
        payment_type=payment_type,
        is_paid=True,
        paid_at=now,
        created_by=created_by,
    )

    # 5. Transition booking
    booking.status = Booking.BookingStatus.PAID
    booking.save(update_fields=["status", "updated_at"])

    # --- Audit + Notification ---
    log_action(
        account=created_by,
        action="payment.recorded",
        entity_type="Payment",
        entity_id=payment.pk,
        after_data={
            "id": payment.pk,
            "booking_id": booking.pk,
            "amount": str(amount),
            "payment_type": payment_type,
            "is_paid": True,
            "booking_status": booking.status,
        },
    )
    notify_roles(
        roles=["administrator", "director"],
        branch=booking.branch,
        notification_type="payment",
        message=f"Payment #{payment.pk} recorded for booking #{booking.pk} "
                f"(amount: {amount}).",
    )

    return payment
