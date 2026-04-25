"""
Security middleware for the Hostel Management System (Steps 21 & 21.2).

Middleware classes:
    - SecurityHeadersMiddleware: Adds CSP and Permissions-Policy headers.
    - SecurityLoggingMiddleware: Logs auth failures, permission denials,
      rate-limit hits, and server errors.  Now also feeds events into
      the suspicious-activity detection service (Step 21.2).
    - BlockedUserMiddleware: Rejects requests from blocked IPs / accounts
      with 403 Forbidden (Step 21.2).

References:
    - README Section 16.6 (Security)
    - README Section 23 (Logging Strategy)
    - README Section 25.5 (Security Implementation Details)
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

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

    Step 21.2: Also feeds 401/403/429 events into the suspicious-activity
    detection service so that repeated offenders get auto-blocked.
    """

    # Map HTTP status → suspicious-activity type for the detection service.
    # 401 is split based on the request path so that an expired JWT on a
    # normal API call is not misclassified as a failed login attempt.
    _STATUS_TO_ACTIVITY: dict[int, str] = {
        403: "unauthorized_access",
        429: "rate_limit_exceeded",
    }

    # Paths that are *real* authentication endpoints. Only a 401 on one of
    # these counts as a failed_login attempt; any other 401 (expired token,
    # missing auth header on a normal endpoint, …) is logged as a generic
    # ``unauthorized_access`` so the suspicious-activity dashboard isn't
    # flooded with noise from legitimate users whose session lapsed.
    _LOGIN_PATH_PREFIXES: tuple[str, ...] = (
        "/api/v1/auth/login/",
        "/api/v1/auth/telegram/",
        "/api/v1/auth/token/refresh/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start_time

        status_code = response.status_code
        if status_code in (401, 403, 429) or status_code >= 500:
            client_ip = self._get_client_ip(request)
            user = getattr(request, "user", None)
            user_info = self._resolve_user_info(user)

            self._log_event(status_code, client_ip, request.method, request.path, user_info, duration)
            self._feed_detection(status_code, client_ip, user, request.path)

        return response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_event(self, status_code, client_ip, method, path, user_info, duration):
        """Emit the appropriate log line for the response status code."""
        _LOG_TEMPLATES = {
            401: ("AUTH_FAILED | ip=%s | %s %s | user=%s | %.3fs", logger.warning),
            403: ("PERMISSION_DENIED | ip=%s | %s %s | user=%s | %.3fs", logger.warning),
            429: ("RATE_LIMITED | ip=%s | %s %s | user=%s | %.3fs", logger.warning),
        }
        entry = _LOG_TEMPLATES.get(status_code)
        if entry:
            template, log_fn = entry
            log_fn(template, client_ip, method, path, user_info, duration)
        elif status_code >= 500:
            logger.error(
                "SERVER_ERROR | ip=%s | %s %s | user=%s | status=%d | %.3fs",
                client_ip, method, path, user_info, status_code, duration,
            )

    def _feed_detection(self, status_code, client_ip, user, path):
        """Feed event into the suspicious-activity detection service (Step 21.2)."""
        if status_code == 401:
            # Only count as failed_login when the request actually hit a
            # login / token endpoint. Any other 401 is a generic auth issue
            # (expired access token on a normal API call) and gets logged
            # as ``unauthorized_access`` instead.
            if any(path.startswith(p) for p in self._LOGIN_PATH_PREFIXES):
                activity_type = "failed_login"
            else:
                activity_type = "unauthorized_access"
        else:
            activity_type = self._STATUS_TO_ACTIVITY.get(status_code)
        if not activity_type:
            return
        try:
            from config.security.detection import track_suspicious_activity

            account = user if user and getattr(user, "is_authenticated", False) else None
            track_suspicious_activity(
                ip_address=client_ip,
                activity_type=activity_type,
                account=account,
            )
        except Exception:  # noqa: BLE001 — never let detection crash request
            logger.exception("Detection service error")

    @staticmethod
    def _resolve_user_info(user) -> str:
        if user and getattr(user, "is_authenticated", False):
            return str(user)
        return "anonymous"

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class BlockedUserMiddleware:
    """
    Reject requests from blocked IPs / accounts with 403 Forbidden (Step 21.2).

    This middleware runs early in the stack (right after
    ``AuthenticationMiddleware``) so that blocked callers are rejected
    before any view logic executes.

    The ``is_blocked()`` call is lightweight — a single indexed query —
    and also garbage-collects expired blocks automatically.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        client_ip = self._get_client_ip(request)
        user = getattr(request, "user", None)
        account = (
            user
            if user and getattr(user, "is_authenticated", False)
            else None
        )

        try:
            from config.security.detection import is_blocked

            if is_blocked(ip_address=client_ip, account=account):
                logger.warning(
                    "REQUEST_BLOCKED | ip=%s | %s %s | account=%s",
                    client_ip, request.method, request.path, account or "anonymous",
                )
                return JsonResponse(
                    {
                        "success": False,
                        "error": {
                            "code": "blocked",
                            "message": (
                                "Your access has been temporarily blocked due to "
                                "suspicious activity. Please try again later."
                            ),
                        },
                    },
                    status=403,
                )
        except Exception:  # noqa: BLE001 — never let detection crash request
            logger.exception("BlockedUserMiddleware error")

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Extract client IP, respecting X-Forwarded-For behind reverse proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
