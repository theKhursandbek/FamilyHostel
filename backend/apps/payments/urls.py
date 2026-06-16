"""
Payments URL configuration.

API endpoints:
    /api/v1/payments/payments/  — CRUD (README Section 17)
    /api/v1/payments/webhook/   — Stripe webhook (README Section 26.1)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .client_views import (
    BookingDraftStatusView,
    DemoConfirmDraftView,
    GuestBookingCancelView,
    GuestBookingDetailView,
    GuestBookingsView,
    MyPaymentsView,
    StripeDraftIntentForExtensionView,
    StripeDraftIntentForRoomView,
    StripeIntentView,
)
from .views import PaymentViewSet, SalaryRecordViewSet, StripeWebhookView

app_name = "payments"

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("salary", SalaryRecordViewSet, basename="salary-record")

urlpatterns = [
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    # Client-facing (Telegram Mini App)
    path("stripe/intent/", StripeIntentView.as_view(), name="stripe-intent"),
    path("my/", MyPaymentsView.as_view(), name="my-payments"),
    # Mini App payment-first flow (plan §4.2, D5)
    path("draft/room/", StripeDraftIntentForRoomView.as_view(), name="draft-room"),
    path("draft/extension/", StripeDraftIntentForExtensionView.as_view(), name="draft-extension"),
    path("drafts/<uuid:pk>/", BookingDraftStatusView.as_view(), name="draft-status"),
    path("drafts/<uuid:pk>/demo-confirm/", DemoConfirmDraftView.as_view(), name="draft-demo-confirm"),
    # Guest bookings — looked up by phone (no auth)
    path("guest/bookings/", GuestBookingsView.as_view(), name="guest-bookings"),
    path("guest/bookings/<int:pk>/", GuestBookingDetailView.as_view(), name="guest-booking-detail"),
    path(
        "guest/bookings/<int:pk>/cancel/",
        GuestBookingCancelView.as_view(),
        name="guest-booking-cancel",
    ),
    path("", include(router.urls)),
]
