"""
Offline settings — SQLite for migration generation when PostgreSQL is unavailable.
"""

from .development import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
