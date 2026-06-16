"""
Data migration — booking source normalisation + per-branch numbering.

Two backfills, both idempotent:

1. **Source normalisation.** The old ``walk_in`` channel was merged into
   ``manual`` (plan §5). Any legacy rows carrying ``source='walk_in'`` are
   rewritten to ``manual`` so they match the new two-value enum.

2. **Per-branch sequence numbers.** ``Booking.branch_number`` was just added
   as a nullable column. Here we assign every existing booking its
   per-branch sequence (Branch A #1, #2, …; Branch B #1, #2, …) in *creation
   order* (``id`` ascending), starting from each branch's current maximum so
   the migration can be safely re-run.
"""

from collections import defaultdict

from django.db import migrations
from django.db.models import Max


def backfill(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")

    # 1) walk_in → manual (legacy value no longer in the enum).
    Booking.objects.filter(source="walk_in").update(source="manual")

    # 2) Per-branch numbering, resuming from each branch's current max so the
    #    operation is idempotent and never collides with the unique constraint.
    existing_max = {
        row["branch_id"]: row["m"]
        for row in (
            Booking.objects.exclude(branch_number__isnull=True)
            .values("branch_id")
            .annotate(m=Max("branch_number"))
        )
    }
    counters = defaultdict(int, existing_max)

    to_update = []
    pending = Booking.objects.filter(branch_number__isnull=True).order_by(
        "branch_id", "id"
    )
    for booking in pending.iterator():
        counters[booking.branch_id] += 1
        booking.branch_number = counters[booking.branch_id]
        to_update.append(booking)

    if to_update:
        Booking.objects.bulk_update(to_update, ["branch_number"], batch_size=500)


def unbackfill(apps, schema_editor):
    """Reverse only the numbering (source rewrite is intentionally lossy)."""
    Booking = apps.get_model("bookings", "Booking")
    Booking.objects.update(branch_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_booking_extension_branch_number"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
