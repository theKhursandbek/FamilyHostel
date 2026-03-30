"""
Staff URL configuration.

API endpoints: /api/v1/staff/ (attendance, shifts)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttendanceViewSet, ShiftAssignmentViewSet

app_name = "staff"

router = DefaultRouter()
router.register("shifts", ShiftAssignmentViewSet, basename="shift-assignment")
router.register("attendance", AttendanceViewSet, basename="attendance")

urlpatterns = [
    path("", include(router.urls)),
]
