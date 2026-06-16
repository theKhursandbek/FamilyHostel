"""Public Telegram Mini App URL routes (no authentication required)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import (
    PublicBranchViewSet,
    PublicLocationsView,
    PublicRoomTypeViewSet,
    PublicRoomViewSet,
)

app_name = "branches_public"

router = DefaultRouter()
router.register("branches", PublicBranchViewSet, basename="public-branch")
router.register("rooms", PublicRoomViewSet, basename="public-room")
router.register("room-types", PublicRoomTypeViewSet, basename="public-room-type")

urlpatterns = [
    path("locations/", PublicLocationsView.as_view(), name="public-locations"),
    path("", include(router.urls)),
]
