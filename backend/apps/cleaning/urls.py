"""
Cleaning URL configuration.

API endpoints: /api/v1/cleaning/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CleaningTaskViewSet

app_name = "cleaning"

router = DefaultRouter()
router.register("tasks", CleaningTaskViewSet, basename="cleaning-task")

urlpatterns = [
    path("", include(router.urls)),
]
