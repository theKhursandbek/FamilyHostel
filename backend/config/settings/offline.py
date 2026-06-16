"""
Offline settings for Hostel Management System.
Used for CI/CD checks, collectstatic, and running tests/commands without external dependencies.
"""

from .base import *  # noqa

# Disable debug
DEBUG = False

# Use SQLite for offline/CI checks to avoid needing a live Postgres instance
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Dummy Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Celery: Eager mode, no broker
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Redis Channels: In-memory
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Ignore staticfiles manifest errors when running checks without collectstatic
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
