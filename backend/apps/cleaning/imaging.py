"""
Image hygiene for cleaning verification photos.

Responsibilities:
    - Honour EXIF orientation, then STRIP all EXIF (privacy + anti-spoofing).
    - Down-scale to a sane maximum edge.
    - Re-encode as JPEG at a fixed quality (storage discipline).
    - Report final dimensions + byte size for accounting.

Used by the cleaning upload endpoint so staff phone photos (~3-5 MB raw)
become ~250-350 KB normalised JPEGs before they ever hit storage.
"""

from __future__ import annotations

import io

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def normalize_image(django_file, *, filename: str = "clean.jpg") -> tuple[ContentFile, int, int, int]:
    """Normalise an uploaded image file.

    Args:
        django_file: An uploaded file-like object (DRF ``ImageField`` value).
        filename: Name to assign the returned ``ContentFile``.

    Returns:
        ``(content_file, width, height, byte_size)`` where ``content_file``
        is a clean, EXIF-stripped, down-scaled JPEG ready to persist.

    Raises:
        ValueError: If the file cannot be opened as an image.
    """
    max_edge = int(getattr(settings, "CLEANING_IMAGE_MAX_EDGE", 1600))
    quality = int(getattr(settings, "CLEANING_IMAGE_JPEG_QUALITY", 75))

    try:
        img = Image.open(django_file)
        # Apply EXIF orientation so the visible pixels are upright...
        transposed = ImageOps.exif_transpose(img)
        if transposed is not None:
            img = transposed
    except Exception as exc:  # noqa: BLE001 - surface as a clean validation error
        raise ValueError("Uploaded file is not a valid image.") from exc

    # Flatten transparency / palette modes to RGB for JPEG.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Down-scale preserving aspect ratio (no upscaling).
    img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    width, height = img.size

    # Re-encode WITHOUT EXIF (a fresh buffer carries no original metadata).
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    data = buffer.getvalue()

    if not filename.lower().endswith((".jpg", ".jpeg")):
        filename = f"{filename.rsplit('.', 1)[0]}.jpg"

    return ContentFile(data, name=filename), width, height, len(data)
