"""
Django production settings for Hostel Management System.

Extends base.py with production-specific overrides.
Deploy on Azure App Service (README Section 16.4).
"""

from .base import *  # noqa: F401, F403

# ==============================================================================
# PRODUCTION OVERRIDES
# ==============================================================================

DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")  # noqa: F405

# ==============================================================================
# SECURITY
# ==============================================================================

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==============================================================================
# CORS — Restrict in production
# ==============================================================================

CORS_ALLOW_ALL_ORIGINS = False
# CORS_ALLOWED_ORIGINS should be set in .env or here
