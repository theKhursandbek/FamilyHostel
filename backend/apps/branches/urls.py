"""
Branches URL configuration.

API endpoint: /api/v1/branches/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BranchViewSet, RoomTypeViewSet, RoomViewSet

app_name = "branches"

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("room-types", RoomTypeViewSet, basename="room-type")
router.register("rooms", RoomViewSet, basename="room")

urlpatterns = [
    path("", include(router.urls)),
]
