"""
Custom exception handler for REST Framework API responses.

Provides consistent error response formatting across all API endpoints.
"""

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Custom exception handler that wraps DRF's default handler.

    Ensures all API errors return consistent response format with
    'detail' and optional 'code' fields.

    Args:
        exc: The exception instance
        context: Additional context about the exception

    Returns:
        Response object with formatted error
    """
    # Use DRF's default exception handler first
    response = drf_exception_handler(exc, context)

    # If DRF's handler couldn't handle it, return a 500 error
    if response is None:
        return Response(
            {"detail": "Internal server error"},
            status=500
        )

    # Ensure consistent error response format
    if "detail" not in response.data:
        response.data = {
            "detail": str(exc),
            "code": getattr(exc, "default_code", "error"),
        }

    return response
