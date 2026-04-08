"""
Custom DRF exception handler (Step 20).

Wraps **all** error responses in a standardised envelope::

    {
        "success": false,
        "error": {
            "code": "<ERROR_CODE>",
            "message": "<human-readable message>"
        }
    }

Handles:
    - ValidationError         → ``validation_error``
    - AuthenticationFailed    → ``authentication_failed``
    - NotAuthenticated        → ``not_authenticated``
    - PermissionDenied        → ``permission_denied``
    - NotFound / Http404      → ``not_found``
    - MethodNotAllowed        → ``method_not_allowed``
    - Throttled               → ``throttled``
    - ParseError              → ``parse_error``
    - Any other APIException  → ``api_error``
    - Unhandled 500           → ``server_error``
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from config.api.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)

__all__ = ["custom_exception_handler"]


# Map exception class → (code, default_message)
_EXCEPTION_MAP: dict[type, tuple[str, str]] = {
    ValidationError: ("validation_error", "Invalid input."),
    AuthenticationFailed: ("authentication_failed", "Authentication credentials were invalid."),
    NotAuthenticated: ("not_authenticated", "Authentication credentials were not provided."),
    PermissionDenied: ("permission_denied", "You do not have permission to perform this action."),
    NotFound: ("not_found", "The requested resource was not found."),
    Http404: ("not_found", "The requested resource was not found."),
    MethodNotAllowed: ("method_not_allowed", "HTTP method not allowed."),
    Throttled: ("throttled", "Request was throttled. Please try again later."),
    ParseError: ("parse_error", "Malformed request."),
    ServiceUnavailable: ("service_unavailable", "Service temporarily unavailable."),
}


def _flatten_errors(detail: Any) -> str:
    """Convert DRF error detail into a single human-readable string."""
    if isinstance(detail, list):
        return " ".join(str(item) for item in detail)
    if isinstance(detail, dict):
        parts: list[str] = []
        for field, messages in detail.items():
            if isinstance(messages, list):
                msg_str = " ".join(str(m) for m in messages)
            else:
                msg_str = str(messages)
            if field == "non_field_errors" or field == "detail":
                parts.append(msg_str)
            else:
                parts.append(f"{field}: {msg_str}")
        return " ".join(parts)
    return str(detail)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    DRF exception handler that returns a standard error envelope.

    Set as ``REST_FRAMEWORK["EXCEPTION_HANDLER"]`` in settings.
    """
    # Let DRF handle its own exceptions first (sets headers, etc.)
    response = drf_exception_handler(exc, context)

    if response is not None:
        # Known DRF exception — check class hierarchy for mapping
        code = "api_error"
        default_msg = "An error occurred."
        for cls in type(exc).__mro__:
            if cls in _EXCEPTION_MAP:
                code, default_msg = _EXCEPTION_MAP[cls]
                break

        # For validation errors, keep the structured detail as-is AND provide
        # a flat message.
        if isinstance(exc, ValidationError):
            message = _flatten_errors(response.data)
            error_payload: dict[str, Any] = {
                "code": code,
                "message": message,
                "details": response.data,
            }
        else:
            message = _flatten_errors(response.data)
            error_payload = {
                "code": code,
                "message": message,
            }

        response.data = {
            "success": False,
            "error": error_payload,
        }
        return response

    # Unhandled exception → 500
    logger.exception("Unhandled exception in API view: %s", exc)

    return Response(
        {
            "success": False,
            "error": {
                "code": "server_error",
                "message": "An internal server error occurred.",
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
