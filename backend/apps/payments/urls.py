"""
Payments URL configuration.

API endpoint: /api/v1/payments/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet

app_name = "payments"

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
]
