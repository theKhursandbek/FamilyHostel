"""
Django development settings for Hostel Management System.

Extends base.py with development-specific overrides.
"""

from .base import *  # noqa: F401, F403  # NOSONAR — standard Django settings pattern

# ==============================================================================
# DEVELOPMENT OVERRIDES
# ==============================================================================

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# ==============================================================================
# CORS — Allow all in development
# ==============================================================================

CORS_ALLOW_ALL_ORIGINS = True

# ==============================================================================
# DRF — Add Browsable API in development
# ==============================================================================

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# ==============================================================================
# EMAIL — Console backend in development
# ==============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
