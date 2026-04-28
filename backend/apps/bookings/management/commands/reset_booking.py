"""
Dev-only helper to fully reset a booking back to ``pending`` *and* delete
its payment rows so you can retest the Pay / Complete flow.

Usage:
    python manage.py reset_booking 14
    python manage.py reset_booking 14 15 16
    python manage.py reset_booking --all-active   # all non-canceled, non-completed
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.models import Booking
from apps.payments.models import Payment


class Command(BaseCommand):
    help = "Reset bookings to 'pending' and wipe their payment history (DEV ONLY)."

    def add_arguments(self, parser):
        parser.add_argument(
            "booking_ids",
            nargs="*",
            type=int,
            help="One or more booking IDs to reset.",
        )
        parser.add_argument(
            "--all-active",
            action="store_true",
            help="Reset every booking that isn't canceled or completed.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        ids = opts["booking_ids"]
        if opts["all_active"]:
            qs = Booking.objects.exclude(status__in=["canceled", "completed"])
        elif ids:
            qs = Booking.objects.filter(pk__in=ids)
        else:
            raise CommandError(
                "Pass at least one booking id, or use --all-active."
            )

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No matching bookings."))
            return

        for booking in qs:
            removed, _ = Payment.objects.filter(booking=booking).delete()
            booking.status = Booking.BookingStatus.PENDING
            booking.save(update_fields=["status", "updated_at"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"  #{booking.pk}: status -> pending, "
                    f"deleted {removed} payment row(s)"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Reset {qs.count()} booking(s)."))
