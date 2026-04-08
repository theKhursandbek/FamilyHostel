"""
Django production settings for Hostel Management System.

Extends base.py with production-specific overrides.
Deploy on Azure App Service (README Section 16.4).
"""

from .base import *  # noqa: F401, F403  # NOSONAR — standard Django settings pattern

# ==============================================================================
# PRODUCTION OVERRIDES
# ==============================================================================

DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")  # noqa: F405

# ==============================================================================
# SECURITY — Transport & Cookie (README Section 25.5 & 26.5)
# ==============================================================================

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==============================================================================
# SECURITY — Headers (Django built-in)
# ==============================================================================

SECURE_CONTENT_TYPE_NOSNIFF = True  # X-Content-Type-Options: nosniff
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ==============================================================================
# SECURITY — Custom Headers (via SecurityHeadersMiddleware)
# ==============================================================================

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "frame-ancestors 'none'"
)

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=()"
)

# ==============================================================================
# SECURITY — Cookie hardening
# ==============================================================================

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ==============================================================================
# CORS — Restrict in production (README Section 26.5)
# ==============================================================================

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405

# ==============================================================================
# CSRF — Trusted origins
# ==============================================================================

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
