"""
Reports URL configuration.

API endpoint: /api/v1/reports/ (README Section 17)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .excel_views import (
    BranchDashboardView,
    WorkbookBranchView,
    WorkbookGeneralManagerView,
    WorkbookListView,
    WorkbookLobarView,
)
from .salary_adjustment_views import SalaryAdjustmentViewSet
from .views import MonthlyReportViewSet

app_name = "reports"

router = DefaultRouter()
router.register("monthly", MonthlyReportViewSet, basename="monthly-report")
router.register(
    "salary-adjustments",
    SalaryAdjustmentViewSet,
    basename="salary-adjustment",
)

urlpatterns = [
    path("workbook/available/", WorkbookListView.as_view(), name="workbook-available"),
    path("workbook/branch/<int:branch_id>/<int:year>/",
         WorkbookBranchView.as_view(), name="workbook-branch"),
    path("workbook/general-manager/<int:director_id>/<int:year>/",
         WorkbookGeneralManagerView.as_view(),
         name="workbook-general-manager"),
    # Deprecated alias — kept for backwards compatibility.
    path("workbook/lobar/<int:year>/",
         WorkbookLobarView.as_view(), name="workbook-lobar"),
    path("branch-dashboard/",
         BranchDashboardView.as_view(), name="branch-dashboard"),
    path("", include(router.urls)),
]

