"""
Payments URL configuration.

API endpoints:
    /api/v1/payments/payments/  — CRUD (README Section 17)
    /api/v1/payments/webhook/   — Stripe webhook (README Section 26.1)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, SalaryRecordViewSet, StripeWebhookView

app_name = "payments"

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("salary", SalaryRecordViewSet, basename="salary-record")

urlpatterns = [
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("", include(router.urls)),
]
