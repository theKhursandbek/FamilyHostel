"""URL patterns for client-side telemetry endpoints."""

from django.urls import path

from .metrics_views import WebVitalsView

urlpatterns = [
    path("web-vitals/", WebVitalsView.as_view(), name="web-vitals"),
]
