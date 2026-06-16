"""
Bookings URL configuration.

API endpoints: /api/v1/bookings/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .client_views import (
    MyBookingCancelView,
    MyBookingDetailView,
    MyBookingsView,
    availability,
)
from .views import BookingViewSet

app_name = "bookings"

router = DefaultRouter()
router.register("bookings", BookingViewSet, basename="booking")

urlpatterns = [
    # Client-facing endpoints (Telegram Mini App).
    # NOTE: this app is mounted at /api/v1/bookings/ in config/urls.py, so
    # paths here MUST NOT start with another `bookings/` segment — that's
    # only kept for the legacy router so existing admin URLs don't break.
    path("availability/", availability, name="booking-availability"),
    path("my/", MyBookingsView.as_view(), name="booking-my-list"),
    path("my/<int:pk>/", MyBookingDetailView.as_view(), name="booking-my-detail"),
    path(
        "my/<int:pk>/cancel/",
        MyBookingCancelView.as_view(),
        name="booking-my-cancel",
    ),
    path("", include(router.urls)),
]
