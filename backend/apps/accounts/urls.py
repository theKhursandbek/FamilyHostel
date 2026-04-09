"""
Accounts URL configuration.

API endpoints (README Section 17 & 25.5):
    POST /api/v1/auth/telegram/         — Telegram Mini App login → JWT tokens
    POST /api/v1/auth/token/refresh/    — Refresh JWT access token
    GET  /api/v1/auth/accounts/         — Account list (admin+)
    GET  /api/v1/auth/accounts/{id}/    — Account detail (admin+)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .authentication import TelegramAuthView
from .admin_login import AdminLoginView
from .views import AccountViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")

urlpatterns = [
    # Admin panel login (phone + password → JWT tokens)
    path("login/", AdminLoginView.as_view(), name="admin-login"),
    # Telegram Mini App authentication (README Section 17 — POST /auth/telegram/)
    path("telegram/", TelegramAuthView.as_view(), name="telegram-auth"),
    # JWT token refresh (README Section 25.5)
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Account management
    path("", include(router.urls)),
]
