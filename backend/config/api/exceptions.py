"""
Custom API exceptions (Step 21).

Provides exception classes not included in DRF's built-in set.
"""

from rest_framework.exceptions import APIException

__all__ = ["ServiceUnavailable"]


class ServiceUnavailable(APIException):
    """503 — service temporarily unavailable."""

    status_code = 503
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"
