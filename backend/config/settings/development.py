"""
Django development settings for Hostel Management System.

Extends base.py with development-specific overrides.
Used for local development and testing.
"""

from .base import *  # noqa: F401, F403  # NOSONAR — standard Django settings pattern

# ==============================================================================
# DEVELOPMENT OVERRIDES
# ==============================================================================

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "*"]

# ==============================================================================
# DATABASE — SQLite (default for development)
# ==============================================================================
# The database configuration from base.py uses SQLite by default,
# which is appropriate for development.

# ==============================================================================
# INSTALLED APPS — Add development tools
# ==============================================================================

# Optionally add django_extensions if available
try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS += ["django_extensions"]  # noqa: F405
except ImportError:
    pass

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

# Development middleware can be added here if needed

# ==============================================================================
# LOGGING — Verbose logging for development
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ==============================================================================
# CELERY — Development settings
# ==============================================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ==============================================================================
# EMAIL — Console backend for development
# ==============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ==============================================================================
# SECURITY — Relaxed for development
# ==============================================================================

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ==============================================================================
# CORS — Allow local dev frontends
# ==============================================================================

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # admin frontend (Vite)
    "http://localhost:5174",   # Telegram Mini App (Vite)
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
