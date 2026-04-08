"""
Security middleware for the Hostel Management System (Step 21).

Middleware classes:
    - SecurityHeadersMiddleware: Adds CSP and Permissions-Policy headers.
    - SecurityLoggingMiddleware: Logs auth failures, permission denials,
      rate-limit hits, and server errors.

References:
    - README Section 16.6 (Security)
    - README Section 23 (Logging Strategy)
    - README Section 25.5 (Security Implementation Details)
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("security")


class SecurityHeadersMiddleware:
    """
    Add security headers not covered by Django's built-in SecurityMiddleware.

    Controlled by settings:
        ``CONTENT_SECURITY_POLICY``  → Content-Security-Policy header
        ``PERMISSIONS_POLICY``       → Permissions-Policy header

    Django's SecurityMiddleware already handles:
        - X-Content-Type-Options  (``SECURE_CONTENT_TYPE_NOSNIFF``)
        - Referrer-Policy         (``SECURE_REFERRER_POLICY``)
        - HSTS                    (``SECURE_HSTS_SECONDS``)
        - X-Frame-Options         (via ``XFrameOptionsMiddleware``)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Read once at startup for performance
        self.csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        self.permissions_policy = getattr(settings, "PERMISSIONS_POLICY", None)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if self.csp:
            response["Content-Security-Policy"] = self.csp

        if self.permissions_policy:
            response["Permissions-Policy"] = self.permissions_policy

        return response


class SecurityLoggingMiddleware:
    """
    Log security-relevant events based on HTTP response status codes.

    Logged events (all include client IP, method, path, user, duration):
        - 401 Unauthorized      → ``AUTH_FAILED``       (warning)
        - 403 Forbidden         → ``PERMISSION_DENIED`` (warning)
        - 429 Too Many Requests → ``RATE_LIMITED``       (warning)
        - 5xx Server Error      → ``SERVER_ERROR``       (error)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start_time

        status_code = response.status_code
        if status_code in (401, 403, 429) or status_code >= 500:
            client_ip = self._get_client_ip(request)
            method = request.method
            path = request.path
            user = getattr(request, "user", None)
            user_info = (
                str(user)
                if user and getattr(user, "is_authenticated", False)
                else "anonymous"
            )

            if status_code == 401:
                logger.warning(
                    "AUTH_FAILED | ip=%s | %s %s | user=%s | %.3fs",
                    client_ip, method, path, user_info, duration,
                )
            elif status_code == 403:
                logger.warning(
                    "PERMISSION_DENIED | ip=%s | %s %s | user=%s | %.3fs",
                    client_ip, method, path, user_info, duration,
                )
            elif status_code == 429:
                logger.warning(
                    "RATE_LIMITED | ip=%s | %s %s | user=%s | %.3fs",
                    client_ip, method, path, user_info, duration,
                )
            else:
                logger.error(
                    "SERVER_ERROR | ip=%s | %s %s | user=%s | status=%d | %.3fs",
                    client_ip, method, path, user_info, status_code, duration,
                )

        return response

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
