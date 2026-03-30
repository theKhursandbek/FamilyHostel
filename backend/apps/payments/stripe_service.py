"""
Stripe payment integration (README Section 25.1 & 26.1).

All Stripe logic lives here — views only call these functions.

Flow:
    1. ``create_payment_intent`` — called when admin initiates online payment
       → creates Stripe PaymentIntent, stores ``payment_intent_id`` on Payment
    2. ``construct_webhook_event`` — verifies Stripe signature
    3. ``process_webhook_event`` — idempotent dispatcher
       → ``_handle_payment_succeeded`` — marks booking as paid
       → ``_handle_payment_failed``  — logs failure

Idempotency:
    - Every processed event ID is stored in ``ProcessedStripeEvent``
    - Re-delivered webhooks are silently ignored
"""

from __future__ import annotations

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.payments.models import Payment, ProcessedStripeEvent
from apps.reports.services import log_action, notify_roles

logger = logging.getLogger(__name__)

__all__ = [
    "create_payment_intent",
    "construct_webhook_event",
    "process_webhook_event",
]


# ---------------------------------------------------------------------------
# 1. Create PaymentIntent
# ---------------------------------------------------------------------------

def create_payment_intent(
    *,
    booking: Booking,
    created_by=None,
) -> Payment:
    """
    Create a Stripe PaymentIntent for the given booking.

    Steps:
        1. Validate booking is ``pending`` and has no existing payment
        2. Call Stripe API to create a PaymentIntent
        3. Create a local Payment record (``is_paid=False``) with the
           ``payment_intent_id``

    Returns:
        The created ``Payment`` instance (not yet paid — awaits webhook).

    Raises:
        ``ValidationError`` on rule violations.
        ``stripe.error.StripeError`` on Stripe API failures.
    """
    # Validate booking status
    if booking.status != Booking.BookingStatus.PENDING:
        raise ValidationError(
            {"booking": f"Cannot create payment for booking with status '{booking.status}'."}
        )

    # Idempotency: check for existing payment (paid or intent in progress)
    if Payment.objects.filter(booking=booking, is_paid=True).exists():
        raise ValidationError(
            {"booking": "This booking has already been paid."}
        )

    # Check if there's already a pending intent for this booking
    existing_intent = Payment.objects.filter(
        booking=booking,
        payment_type=Payment.PaymentType.ONLINE,
        is_paid=False,
        payment_intent_id__isnull=False,
    ).first()
    if existing_intent:
        return existing_intent

    # Convert UZS amount to the smallest unit (Stripe uses integers)
    # UZS is a zero-decimal currency
    amount_int = int(booking.final_price)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    intent = stripe.PaymentIntent.create(
        amount=amount_int,
        currency="uzs",
        metadata={
            "booking_id": str(booking.pk),
            "branch_id": str(booking.branch_id),
        },
        idempotency_key=f"booking_{booking.pk}",
    )

    payment = Payment.objects.create(
        booking=booking,
        amount=booking.final_price,
        payment_type=Payment.PaymentType.ONLINE,
        is_paid=False,
        payment_intent_id=intent.id,
        created_by=created_by,
    )

    # Audit
    log_action(
        account=created_by,
        action="stripe.payment_intent_created",
        entity_type="Payment",
        entity_id=payment.pk,
        after_data={
            "payment_id": payment.pk,
            "booking_id": booking.pk,
            "payment_intent_id": intent.id,
            "amount": str(booking.final_price),
        },
    )

    return payment


# ---------------------------------------------------------------------------
# 2. Construct & verify webhook event
# ---------------------------------------------------------------------------

def construct_webhook_event(
    payload: bytes,
    sig_header: str,
) -> stripe.Event:
    """
    Verify the Stripe webhook signature and return the parsed event.

    Raises:
        ``stripe.error.SignatureVerificationError`` on invalid signature.
        ``ValueError`` on invalid payload.
    """
    return stripe.Webhook.construct_event(
        payload,
        sig_header,
        settings.STRIPE_WEBHOOK_SECRET,
    )


# ---------------------------------------------------------------------------
# 3. Process webhook event (idempotent dispatcher)
# ---------------------------------------------------------------------------

def process_webhook_event(event: stripe.Event) -> bool:
    """
    Idempotent dispatcher for Stripe webhook events.

    Returns:
        ``True`` if the event was processed for the first time.
        ``False`` if it was already processed (duplicate delivery).
    """
    event_id: str = event.id
    event_type: str = event.type

    # Idempotency: check if already processed
    try:
        with transaction.atomic():
            ProcessedStripeEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
            )
    except IntegrityError:
        logger.info("Duplicate Stripe event ignored: %s (%s)", event_id, event_type)
        return False

    # Dispatch
    handlers = {
        "payment_intent.succeeded": _handle_payment_succeeded,
        "payment_intent.payment_failed": _handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler is None:
        logger.info("Unhandled Stripe event type: %s", event_type)
        return True  # Recorded but not actionable

    handler(event)
    return True


# ---------------------------------------------------------------------------
# Internal handlers
# ---------------------------------------------------------------------------

@transaction.atomic
def _handle_payment_succeeded(event: stripe.Event) -> None:
    """
    Handle ``payment_intent.succeeded``.

    Steps:
        1. Find the Payment by ``payment_intent_id``
        2. Mark it as paid
        3. Transition booking to ``paid``
        4. Audit + notify
    """
    payment_intent = event.data.object
    intent_id: str = payment_intent.id

    try:
        payment = Payment.objects.select_related("booking").get(
            payment_intent_id=intent_id,
        )
    except Payment.DoesNotExist:
        logger.warning(
            "PaymentIntent %s not found in database — skipping.", intent_id,
        )
        return

    if payment.is_paid:
        logger.info("Payment #%s already marked paid — skipping.", payment.pk)
        return

    now = timezone.now()
    payment.is_paid = True
    payment.paid_at = now
    payment.stripe_event_id = event.id
    payment.save(update_fields=["is_paid", "paid_at", "stripe_event_id", "updated_at"])

    booking = payment.booking
    if booking.status == Booking.BookingStatus.PENDING:
        booking.status = Booking.BookingStatus.PAID
        booking.save(update_fields=["status", "updated_at"])

    # Audit
    log_action(
        account=None,
        action="stripe.payment_succeeded",
        entity_type="Payment",
        entity_id=payment.pk,
        after_data={
            "payment_id": payment.pk,
            "booking_id": booking.pk,
            "payment_intent_id": intent_id,
            "stripe_event_id": event.id,
            "amount": str(payment.amount),
            "booking_status": booking.status,
        },
    )

    # Notify
    notify_roles(
        roles=["administrator", "director"],
        branch=booking.branch,
        notification_type="payment",
        message=(
            f"Online payment #{payment.pk} succeeded for booking #{booking.pk} "
            f"(amount: {payment.amount} UZS)."
        ),
    )

    logger.info(
        "PaymentIntent %s succeeded — Payment #%s, Booking #%s → paid",
        intent_id, payment.pk, booking.pk,
    )


def _handle_payment_failed(event: stripe.Event) -> None:
    """
    Handle ``payment_intent.payment_failed``.

    Logs the failure; does NOT change booking status (client can retry).
    """
    payment_intent = event.data.object
    intent_id: str = payment_intent.id
    failure_message: str = getattr(
        payment_intent.last_payment_error, "message", "Unknown error"
    ) if payment_intent.last_payment_error else "Unknown error"

    logger.warning(
        "PaymentIntent %s failed: %s", intent_id, failure_message,
    )

    # Try to find the Payment to record the event
    try:
        payment = Payment.objects.select_related("booking").get(
            payment_intent_id=intent_id,
        )
    except Payment.DoesNotExist:
        logger.warning(
            "PaymentIntent %s not found in database — failure logged only.", intent_id,
        )
        return

    # Audit the failure (but don't change status)
    log_action(
        account=None,
        action="stripe.payment_failed",
        entity_type="Payment",
        entity_id=payment.pk,
        after_data={
            "payment_id": payment.pk,
            "booking_id": payment.booking_id,
            "payment_intent_id": intent_id,
            "stripe_event_id": event.id,
            "failure_message": failure_message,
        },
    )
