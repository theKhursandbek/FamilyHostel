"""
Config package — ensure Celery app is loaded when Django starts.

This import guarantees that ``@shared_task`` decorators pick up the
Celery app instance created in ``config.celery``.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
