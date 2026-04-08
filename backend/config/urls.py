"""
URL configuration for Hostel Management System.

API Base: /api/v1/ (README Section 17)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/branches/", include("apps.branches.urls")),
    path("api/v1/bookings/", include("apps.bookings.urls")),
    path("api/v1/staff/", include("apps.staff.urls")),
    path("api/v1/cleaning/", include("apps.cleaning.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/penalties/", include("apps.reports.penalty_urls")),
    path("api/v1/facility-logs/", include("apps.reports.facility_urls")),
    path("api/v1/admin-panel/", include("apps.admin_panel.urls")),
    path("api/v1/dashboard/", include("apps.admin_panel.dashboard_urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
