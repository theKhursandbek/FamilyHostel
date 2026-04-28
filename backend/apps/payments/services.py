"""
Payment business logic (README Section 14.4 & 14.10).

Rules:
    - A booking may receive multiple payments (top-ups after extension).
    - Refunds are recorded as Payment rows with negative ``amount``.
    - The booking flips to ``paid`` only when ``balance_due`` reaches 0.
    - Overpayment is rejected.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.reports.services import log_action, notify_roles

__all__ = [
    "record_payment",
    "record_refund",
    "paid_total",
    "balance_due",
]


def _resolve_administrator(user):
    """
    Payment.created_by is FK to Administrator, but views pass request.user
    (an Account). Resolve transparently. Returns None if user has no
    Administrator profile (e.g. director-only, system tasks, anonymous).
    """
    if user is None:
        return None
    # Already an Administrator instance.
    if user.__class__.__name__ == "Administrator":
        return user
    return getattr(user, "administrator", None)


def paid_total(booking: Booking) -> Decimal:
    """Sum of all successful Payment.amount for a booking (refunds are negative)."""
    total = (
        Payment.objects
        .filter(booking=booking, is_paid=True)
        .aggregate(total=Sum("amount"))
        .get("total")
    )
    return Decimal(total or 0)


def balance_due(booking: Booking) -> Decimal:
    """How much the guest still owes. Negative if overpaid (shouldn't happen)."""
    return Decimal(booking.final_price or 0) - paid_total(booking)


@transaction.atomic
def record_payment(
    *,
    booking: Booking,
    amount,
    payment_type: str,
    method: str = Payment.PaymentMethod.CASH,
    created_by=None,
) -> Payment:
    """
    Record a payment (or top-up) and transition the booking to ``paid`` once
    the full balance is settled.

    Rules:
        - Booking must be in ``pending`` status (i.e. there is still a balance).
        - ``amount`` must be > 0 and <= current balance_due (no overpayment).
        - When balance hits 0, status flips to ``paid``.
    """
    if booking.status not in (
        Booking.BookingStatus.PENDING,
        Booking.BookingStatus.PAID,
    ):
        raise ValidationError(
            {"booking": f"Cannot pay for a booking with status '{booking.status}'."}
        )

    amount = Decimal(amount or 0)
    if amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})

    outstanding = balance_due(booking)
    if outstanding <= 0:
        raise ValidationError(
            {"booking": "Cannot pay — this booking is already fully paid."},
        )
    if amount > outstanding:
        raise ValidationError(
            {"amount": f"Amount exceeds balance due ({outstanding})."}
        )

    now = timezone.now()
    payment = Payment.objects.create(
        booking=booking,
        amount=amount,
        payment_type=payment_type,
        method=method,
        is_paid=True,
        paid_at=now,
        created_by=_resolve_administrator(created_by),
    )

    # Flip to paid once nothing is owed.
    new_balance = outstanding - amount
    if new_balance <= 0 and booking.status != Booking.BookingStatus.PAID:
        booking.status = Booking.BookingStatus.PAID
        booking.save(update_fields=["status", "updated_at"])

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
            "method": method,
            "balance_due_after": str(new_balance),
            "booking_status": booking.status,
        },
    )
    notify_roles(
        roles=["administrator", "director"],
        branch=booking.branch,
        notification_type="payment",
        message=(
            f"Payment #{payment.pk} of {amount} UZS recorded for booking "
            f"#{booking.pk} (balance: {max(new_balance, Decimal(0))})."
        ),
    )

    return payment


@transaction.atomic
def record_refund(
    *,
    booking: Booking,
    amount,
    created_by=None,
    reason: str = "early_checkout",
) -> Payment:
    """
    Record a refund as a negative-amount Payment row. Used on early checkout
    or any operator-discretion refund.
    """
    amount = Decimal(amount or 0)
    if amount <= 0:
        raise ValidationError({"amount": "Refund amount must be greater than zero."})

    already_paid = paid_total(booking)
    if amount > already_paid:
        raise ValidationError(
            {"amount": f"Refund exceeds total paid ({already_paid})."}
        )

    payment = Payment.objects.create(
        booking=booking,
        amount=-amount,
        payment_type=Payment.PaymentType.MANUAL,
        is_paid=True,
        paid_at=timezone.now(),
        created_by=_resolve_administrator(created_by),
    )

    log_action(
        account=created_by,
        action="payment.refunded",
        entity_type="Payment",
        entity_id=payment.pk,
        after_data={
            "id": payment.pk,
            "booking_id": booking.pk,
            "amount": str(-amount),
            "reason": reason,
        },
    )
    notify_roles(
        roles=["administrator", "director"],
        branch=booking.branch,
        notification_type="payment",
        message=(
            f"Refund of {amount} UZS issued for booking #{booking.pk} ({reason})."
        ),
    )

    return payment
