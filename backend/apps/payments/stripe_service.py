"""
Stripe service layer — wrapper around stripe-python library.

Handles:
- PaymentIntent creation
- Webhook event verification
- Draft booking/extension payment management
"""

import stripe
from decimal import Decimal


def construct_webhook_event(payload, sig_header, endpoint_secret):
    """
    Verify and construct a Stripe webhook event.

    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
        endpoint_secret: Stripe endpoint secret for webhook verification

    Returns:
        The verified event dict

    Raises:
        stripe.error.InvalidSignatureError: If signature is invalid
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        return event
    except ValueError:
        raise stripe.error.InvalidSignatureError(
            "Payload is not valid JSON", sig_header
        )
    except stripe.error.SignatureVerificationError:
        raise


def process_webhook_event(event):
    """
    Process a verified Stripe webhook event.

    Handles:
    - payment_intent.succeeded
    - payment_intent.payment_failed
    - payment_intent.canceled

    Args:
        event: The webhook event dict from Stripe

    Returns:
        None (event is logged/processed via signals)
    """
    event_type = event.get("type")

    if event_type == "payment_intent.succeeded":
        # Emit signal or trigger task to complete booking
        pass
    elif event_type == "payment_intent.payment_failed":
        # Emit signal or trigger task to fail booking
        pass
    elif event_type == "payment_intent.canceled":
        # Emit signal or trigger task to cancel booking draft
        pass
