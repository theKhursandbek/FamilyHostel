"""
Offline settings — SQLite for migration generation when PostgreSQL is unavailable.
"""

from .development import *  # noqa: F401,F403  # NOSONAR — standard Django settings pattern

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Celery: run tasks synchronously in tests / offline mode
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# DummyCache: ensures throttle counters are never stored,
# effectively disabling rate-limiting during tests.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Channels: in-memory layer for tests (no Redis required)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
