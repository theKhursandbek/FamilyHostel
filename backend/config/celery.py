"""
Celery application configuration (Step 17).

Auto-discovers tasks from all installed Django apps and configures
Redis as broker and result backend.

Usage:
    $ celery -A config worker --loglevel=info
"""

import os

from celery import Celery

# Ensure Django settings are loaded before Celery starts
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("hostel")

# Load Celery-related settings from Django settings (prefix = CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in all INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task — prints its own request info."""
    print(f"Request: {self.request!r}")  # noqa: T201
