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

# Periodic tasks (Celery beat)
app.conf.beat_schedule = {
    # Plan §8 D12 — cancel expired booking/extension drafts every 2 minutes
    # so abandoned PaymentIntents don't drift around in Stripe.
    "reap-stale-drafts": {
        "task": "payments.reap_stale_drafts",
        "schedule": 120.0,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task — prints its own request info."""
    print(f"Request: {self.request!r}")  # noqa: T201
