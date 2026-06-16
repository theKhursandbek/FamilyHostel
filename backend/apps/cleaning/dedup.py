"""
Perceptual-hash duplicate detection for cleaning photos.

Stops a staff member from re-submitting the same (or a near-identical) photo
across rooms/days to fake a cleaning. Each uploaded image gets a 64-bit
perceptual hash (pHash). On upload we compare against recent, non-purged
images from the SAME branch within a rolling window; a Hamming distance at or
below the configured threshold is treated as a duplicate.

Scale note: hostel volume is hundreds of images/month, so a bounded Python
scan is fine. If volume grows, move to a BK-tree or a Postgres
``bit_count(phash # x)`` expression index.
"""

from __future__ import annotations

import datetime
import io

import imagehash
from django.conf import settings
from django.utils import timezone
from PIL import Image


def compute_phash(image_bytes: bytes) -> str:
    """Return the hex perceptual hash for raw image bytes ("" on failure)."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return str(imagehash.phash(img))
    except Exception:  # noqa: BLE001 - a bad image simply has no usable hash
        return ""


def _hamming(hex_a: str, hex_b: str) -> int:
    """Hamming distance between two hex pHash strings (large if unparsable)."""
    try:
        return imagehash.hex_to_hash(hex_a) - imagehash.hex_to_hash(hex_b)
    except (ValueError, TypeError):
        return 999


def find_duplicate(phash_hex: str, *, branch_id: int, exclude_task_id: int | None = None):
    """Find a recent near-duplicate of ``phash_hex`` in the same branch.

    Args:
        phash_hex: The candidate image's hex pHash.
        branch_id: Restrict the search to this branch.
        exclude_task_id: Ignore images belonging to this task (the current one).

    Returns:
        The first matching :class:`CleaningImage`, or ``None``.
    """
    if not phash_hex:
        return None

    from apps.cleaning.models import CleaningImage

    max_distance = int(getattr(settings, "CLEANING_PHASH_MAX_DISTANCE", 5))
    window_days = int(getattr(settings, "CLEANING_PHASH_WINDOW_DAYS", 30))
    since = timezone.now() - datetime.timedelta(days=window_days)

    candidates = (
        CleaningImage.objects.filter(
            task__branch_id=branch_id,
            is_purged=False,
            uploaded_at__gte=since,
        )
        .exclude(phash="")
        .only("id", "phash", "task_id", "zone")
    )
    if exclude_task_id is not None:
        candidates = candidates.exclude(task_id=exclude_task_id)

    for candidate in candidates.iterator():
        if _hamming(phash_hex, candidate.phash) <= max_distance:
            return candidate
    return None
