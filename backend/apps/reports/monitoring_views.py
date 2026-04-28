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

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import SuspiciousActivity
from apps.accounts.permissions import IsDirectorOrHigher, IsSuperAdmin

from .models import AuditLog
from .monitoring_filters import AuditLogFilter, SuspiciousActivityFilter
from .monitoring_serializers import AuditLogSerializer, SuspiciousActivitySerializer
from .restore_service import (
    NotReversibleError,
    RestoreConflictError,
    RestoreError,
    RestoreService,
)

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


    @action(detail=False, methods=["get"], url_path="facets")
    def facets(self, request):
        """Return distinct values for filter dropdowns.

        Scoped to whatever the caller is allowed to see (uses get_queryset).
        Response shape::

            {
              "roles": ["superadmin", "director", ...],
              "actions": ["penalty.created", ...],
              "entity_types": ["Penalty", ...]
            }
        """
        from .audit_actions import ALL_ACTIONS

        qs = self.get_queryset().order_by()
        roles = sorted({
            v for v in qs.values_list("role", flat=True) if v
        })
        # Union of (a) the canonical catalogue defined in audit_actions.py and
        # (b) any dynamic codes already present in the DB (e.g.
        # ``salary_adjustment.bonus_created``, ``cash_session.disputed``).
        actions = sorted(
            set(ALL_ACTIONS)
            | {v for v in qs.values_list("action", flat=True) if v},
        )
        entity_types = sorted({
            v for v in qs.values_list("entity_type", flat=True) if v
        })
        return Response({
            "roles": roles,
            "actions": actions,
            "entity_types": entity_types,
        })

    # ------------------------------------------------------------------
    # Undo / Redo (superadmin only)
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        url_path="undo",
        permission_classes=[IsAuthenticated, IsSuperAdmin],
    )
    def undo(self, request, pk=None):
        return self._restore(request, direction="undo")

    @action(
        detail=True,
        methods=["post"],
        url_path="redo",
        permission_classes=[IsAuthenticated, IsSuperAdmin],
    )
    def redo(self, request, pk=None):
        return self._restore(request, direction="redo")

    def _restore(self, request, *, direction: str) -> Response:
        import logging

        log = logging.getLogger(__name__)
        audit = self.get_object()
        service = RestoreService(actor=request.user)
        try:
            result = service.undo(audit) if direction == "undo" else service.redo(audit)
        except NotReversibleError as exc:
            return Response(
                {"detail": str(exc), "code": "not_reversible"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RestoreConflictError as exc:
            return Response(
                {"detail": str(exc), "code": "conflict"},
                status=status.HTTP_409_CONFLICT,
            )
        except RestoreError as exc:
            return Response(
                {"detail": str(exc), "code": "restore_failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:  # pragma: no cover — last-resort guard
            log.exception(
                "Unexpected error while %sing audit row #%s (action=%s)",
                direction, audit.pk, audit.action,
            )
            return Response(
                {
                    "detail": (
                        f"Could not {direction} this action: {exc.__class__.__name__}: {exc}"
                    ),
                    "code": "unexpected_error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "direction": result.direction,
                "audit_id": result.audit_id,
                "audit_action": result.audit_action,
                "entity_type": result.entity_type,
                "entity_id": result.entity_id,
                "new_audit_id": result.new_audit_id,
                "summary": result.summary,
            },
            status=status.HTTP_200_OK,
        )


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
