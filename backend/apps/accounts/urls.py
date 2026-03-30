"""
Accounts URL configuration.

API endpoint: /api/v1/auth/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AccountViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")

urlpatterns = [
    path("", include(router.urls)),
    # POST /auth/telegram/ — to be implemented
]
