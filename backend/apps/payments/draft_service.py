"""
Draft booking service layer — manage temporary booking drafts before payment.

Plan §4.2 (D5): Guests pay first via Stripe (BookingDraft → Payment webhook →
Booking creation). This service handles creation, status tracking, and cleanup
of draft bookings.
"""

from decimal import Decimal
import stripe


def create_room_booking_draft(room_id, check_in_date, check_out_date, guest_phone=None):
    """
    Create a temporary booking draft for a room.

    Used by the Telegram Mini App when a guest selects a room and is about to
    pay via Stripe. The draft expires after 5 minutes if not confirmed.

    Args:
        room_id: The room being booked
        check_in_date: Check-in date (YYYY-MM-DD)
        check_out_date: Check-out date (YYYY-MM-DD)
        guest_phone: Guest's phone number (optional)

    Returns:
        A dict with:
        {
            "draft_id": "<uuid>",
            "client_secret": "<stripe_secret>",
            "expires_at": "<ISO datetime>",
            "total_price": <Decimal>
        }
    """
    # Placeholder implementation
    return {
        "draft_id": "",
        "client_secret": "",
        "expires_at": None,
        "total_price": Decimal("0"),
    }


def create_extension_draft(booking_id, new_check_out_date, performed_by=None):
    """
    Create a temporary booking extension draft.

    Used when a guest wants to extend an existing booking. Calculates additional
    price and creates a draft for payment.

    Args:
        booking_id: The booking to extend
        new_check_out_date: New check-out date (YYYY-MM-DD)
        performed_by: The account making the request (optional)

    Returns:
        A dict with:
        {
            "draft_id": "<uuid>",
            "client_secret": "<stripe_secret>",
            "expires_at": "<ISO datetime>",
            "additional_price": <Decimal>
        }
    """
    # Placeholder implementation
    return {
        "draft_id": "",
        "client_secret": "",
        "expires_at": None,
        "additional_price": Decimal("0"),
    }
