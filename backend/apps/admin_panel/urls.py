"""
Admin Panel URL configuration.

API endpoint: /api/v1/admin-panel/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .ceo_views import IncomeRuleViewSet, OverrideView, RolePeopleView, SystemSettingsView
from .views import CashSessionViewSet, RoomInspectionViewSet

app_name = "admin_panel"

router = DefaultRouter()
router.register("room-inspections", RoomInspectionViewSet, basename="room-inspection")
router.register("cash-sessions", CashSessionViewSet, basename="cash-session")
router.register("income-rules", IncomeRuleViewSet, basename="income-rule")

urlpatterns = [
    path("system-settings/", SystemSettingsView.as_view(), name="system-settings"),
    path("overrides/", OverrideView.as_view(), name="overrides"),
    path("role-people/<str:role>/", RolePeopleView.as_view(), name="role-people-list"),
    path("role-people/<str:role>/<int:pk>/", RolePeopleView.as_view(), name="role-people-detail"),
    path("", include(router.urls)),
]
