"""
Monitoring views — AuditLog & SuspiciousActivity (SuperAdmin monitoring).

Endpoints:
    Audit Logs:
        GET  /api/v1/audit-logs/          — list (with filtering)
        GET  /api/v1/audit-logs/{id}/     — retrieve

    Suspicious Activities:
        GET  /api/v1/suspicious-activities/          — list (with filtering)
        GET  /api/v1/suspicious-activities/{id}/     — retrieve

Permissions:
    - SuperAdmin: full access across all branches
    - Director: audit logs scoped to own branch accounts only
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import SuspiciousActivity
from apps.accounts.permissions import IsDirectorOrHigher, IsSuperAdmin

from .models import AuditLog
from .monitoring_filters import AuditLogFilter, SuspiciousActivityFilter
from .monitoring_serializers import AuditLogSerializer, SuspiciousActivitySerializer

if TYPE_CHECKING:
    from apps.accounts.models import Account as AccountType


# ==============================================================================
# AUDIT LOG
# ==============================================================================


class AuditLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only access to the audit trail.

    Permission Matrix:
        - SuperAdmin: all audit logs system-wide
        - Director: audit logs for accounts in own branch
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsDirectorOrHigher]
    filterset_class = AuditLogFilter
    ordering_fields = ["created_at", "action", "entity_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = cast("AccountType", self.request.user)
        qs = AuditLog.objects.select_related("account")

        if user.is_superadmin:
            return qs

        # Director — scoped to branch accounts
        director = user.director_profile  # type: ignore[union-attr]
        from apps.accounts.models import Administrator, Staff

        branch_user_ids = set()
        branch_user_ids.update(
            Staff.objects.filter(branch=director.branch).values_list(
                "account_id", flat=True,
            ),
        )
        branch_user_ids.update(
            Administrator.objects.filter(branch=director.branch).values_list(
                "account_id", flat=True,
            ),
        )
        branch_user_ids.add(user.pk)
        return qs.filter(account_id__in=branch_user_ids)


# ==============================================================================
# SUSPICIOUS ACTIVITY
# ==============================================================================


class SuspiciousActivityViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only access to suspicious activity records.

    Permission Matrix:
        - SuperAdmin only: full access
    """

    serializer_class = SuspiciousActivitySerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filterset_class = SuspiciousActivityFilter
    ordering_fields = ["created_at", "updated_at", "count", "activity_type"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        return SuspiciousActivity.objects.select_related("account")
