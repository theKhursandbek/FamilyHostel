"""
Penalty URL configuration (Step 21.7).

API endpoint: /api/v1/penalties/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PenaltyViewSet

app_name = "penalties"

router = DefaultRouter()
router.register("", PenaltyViewSet, basename="penalty")

urlpatterns = [
    path("", include(router.urls)),
]
