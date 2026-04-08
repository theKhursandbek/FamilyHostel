"""
Admin Panel URL configuration.

API endpoint: /api/v1/admin-panel/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CashSessionViewSet, RoomInspectionViewSet

app_name = "admin_panel"

router = DefaultRouter()
router.register("room-inspections", RoomInspectionViewSet, basename="room-inspection")
router.register("cash-sessions", CashSessionViewSet, basename="cash-session")

urlpatterns = [
    path("", include(router.urls)),
]
