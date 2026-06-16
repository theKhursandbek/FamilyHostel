"""
Django production settings for Hostel Management System.

Extends base.py with production-specific overrides.
Deploy on Azure App Service (README Section 16.4).
"""

import dj_database_url
import sentry_sdk

from .base import *  # noqa: F401, F403  # NOSONAR — standard Django settings pattern

# ==============================================================================
# PRODUCTION OVERRIDES
# ==============================================================================

DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")  # noqa: F405

# ==============================================================================
# DATABASE — Azure Database for PostgreSQL (Step 24)
#
# If DATABASE_URL is set (Azure App Service convention), it takes priority.
# Otherwise, fall back to individual DB_* env vars from base.py.
# ==============================================================================

_database_url = env("DATABASE_URL", default="")  # noqa: F405
if _database_url:
    DATABASES["default"] = dj_database_url.parse(  # noqa: F405
        _database_url,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=env.bool("DB_SSL_REQUIRE", default=True),  # noqa: F405
    )
    DATABASES["default"]["ATOMIC_REQUESTS"] = True  # noqa: F405

# ==============================================================================
# STATIC FILES — WhiteNoise (Step 24)
# ==============================================================================

MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==============================================================================
# MEDIA FILES — Azure Blob Storage (Step 24)
#
# When AZURE_STORAGE_ACCOUNT_NAME is set, media files are stored in Azure Blob.
# Otherwise, media falls back to local filesystem (Docker volume).
# ==============================================================================

_azure_account = env("AZURE_STORAGE_ACCOUNT_NAME", default="")  # noqa: F405
if _azure_account:
    STORAGES = {  # noqa: F811
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "azure_container": env(  # noqa: F405
                    "AZURE_STORAGE_CONTAINER_NAME", default="media"
                ),
                "account_name": _azure_account,
                "account_key": env("AZURE_STORAGE_ACCOUNT_KEY", default=""),  # noqa: F405
                "overwrite_files": True,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# ==============================================================================
# SENTRY — Error tracking (Step 24)
# ==============================================================================

_sentry_dsn = env("SENTRY_DSN", default="")  # noqa: F405
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),  # noqa: F405
        profiles_sample_rate=env.float("SENTRY_PROFILES_SAMPLE_RATE", default=0.1),  # noqa: F405
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
    )

# ==============================================================================
# SECURITY — Transport & Cookie (README Section 25.5 & 26.5)
# ==============================================================================

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
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
