"""
Custom API exceptions for consistent error responses.
"""

from rest_framework.exceptions import APIException


class ServiceUnavailable(APIException):
    """Service is temporarily unavailable."""

    status_code = 503
    default_detail = "Service is temporarily unavailable."
    default_code = "service_unavailable"
