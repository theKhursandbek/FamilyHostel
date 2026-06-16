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

from .authentication import TelegramAuthView
from .admin_login import AdminLoginView
from .client_auth import ClientLoginView, ClientRegisterView
from .otp_views import PhoneOtpStartView, PhoneOtpVerifyView
from .telegram_otp_views import TelegramOtpSendView
from .password_views import ChangePasswordView, ResetPasswordView
from .profile_views import CompleteProfileView, MeView
from .token_views import SafeTokenRefreshView
from .views import AccountViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")

urlpatterns = [
    # Admin panel login (phone + password → JWT tokens)
    path("login/", AdminLoginView.as_view(), name="admin-login"),
    # Mini App client registration + password login
    path("register/", ClientRegisterView.as_view(), name="client-register"),
    path("client/login/", ClientLoginView.as_view(), name="client-login"),
    # Telegram Mini App authentication (README Section 17 — POST /auth/telegram/)
    path("telegram/", TelegramAuthView.as_view(), name="telegram-auth"),
    # Mini App phone OTP onboarding (TELEGRAM_MINI_APP_PLAN.md §3.1)
    path(
        "telegram/phone/start/",
        PhoneOtpStartView.as_view(),
        name="telegram-phone-start",
    ),
    path(
        "telegram/phone/verify/",
        PhoneOtpVerifyView.as_view(),
        name="telegram-phone-verify",
    ),
    # JWT token refresh (README Section 25.5)
    path("token/refresh/", SafeTokenRefreshView.as_view(), name="token-refresh"),
    # Telegram OTP dispatch (register / change_password / forgot_password)
    path(
        "otp/telegram/send/",
        TelegramOtpSendView.as_view(),
        name="otp-telegram-send",
    ),
    # Password management
    path("password/change/", ChangePasswordView.as_view(), name="password-change"),
    path("password/reset/", ResetPasswordView.as_view(), name="password-reset"),
    # Mini App self-service profile
    path("me/", MeView.as_view(), name="me"),
    path("profile/", CompleteProfileView.as_view(), name="complete-profile"),
    # Account management
    path("", include(router.urls)),
]
