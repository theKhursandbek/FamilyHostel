"""
Reports URL configuration.

API endpoint: /api/v1/reports/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MonthlyReportViewSet

app_name = "reports"

router = DefaultRouter()
router.register("monthly", MonthlyReportViewSet, basename="monthly-report")

urlpatterns = [
    path("", include(router.urls)),
]
