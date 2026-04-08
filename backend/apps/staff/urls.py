"""
Staff URL configuration.

API endpoints: /api/v1/staff/ (attendance, shifts, day-off requests)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttendanceViewSet, DayOffRequestViewSet, ShiftAssignmentViewSet

app_name = "staff"

router = DefaultRouter()
router.register("shifts", ShiftAssignmentViewSet, basename="shift-assignment")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("day-off-requests", DayOffRequestViewSet, basename="day-off-request")

urlpatterns = [
    path("", include(router.urls)),
]
