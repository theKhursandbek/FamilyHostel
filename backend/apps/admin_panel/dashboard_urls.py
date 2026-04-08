"""
Dashboard URL configuration (Step 21.3).

API endpoints:
    GET /api/v1/dashboard/admin/
    GET /api/v1/dashboard/director/
    GET /api/v1/dashboard/super-admin/
"""

from django.urls import path

from apps.admin_panel.dashboard_views import (
    AdminDashboardView,
    DirectorDashboardView,
    SuperAdminDashboardView,
)

app_name = "dashboard"

urlpatterns = [
    path("admin/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("director/", DirectorDashboardView.as_view(), name="director-dashboard"),
    path("super-admin/", SuperAdminDashboardView.as_view(), name="superadmin-dashboard"),
]
