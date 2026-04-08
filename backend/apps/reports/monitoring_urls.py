"""
URL routing for monitoring endpoints — AuditLog & SuspiciousActivity.

Mounted at:
    /api/v1/audit-logs/              → AuditLogViewSet
    /api/v1/suspicious-activities/   → SuspiciousActivityViewSet
"""

from rest_framework.routers import DefaultRouter

from .monitoring_views import AuditLogViewSet, SuspiciousActivityViewSet

router = DefaultRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register(
    "suspicious-activities",
    SuspiciousActivityViewSet,
    basename="suspicious-activity",
)

app_name = "monitoring"
urlpatterns = router.urls
