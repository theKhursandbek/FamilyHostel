"""
Facility Log URL configuration (Step 21.7).

API endpoint: /api/v1/facility-logs/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FacilityLogViewSet

app_name = "facility_logs"

router = DefaultRouter()
router.register("", FacilityLogViewSet, basename="facility-log")

urlpatterns = [
    path("", include(router.urls)),
]
