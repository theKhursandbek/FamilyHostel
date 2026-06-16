"""Accounts views (README Section 17)."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.branches.models import Branch
from apps.reports.audit_mixin import AuditedModelViewSetMixin

from .models import Account, Director
from .permissions import IsAdminOrHigher, IsSuperAdmin
from .serializers import AccountSerializer


class AccountViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """Account management endpoints.

    - **List / Retrieve**: any authenticated Admin / Director / Super Admin.
    - **Create / Update / Delete / Disable / Enable**: Super Admin only
      (per README Section 3.1 — "Create and manage all roles").
    """

    audit_entity_type = "Account"
    audit_action_prefix = "account"

    queryset = Account.objects.prefetch_related(
        "client_profile",
        "staff_profile__branch",
        "administrator_profile__branch",
        "director_profile__branch",
        "superadmin_profile",
    )
    serializer_class = AccountSerializer
    ordering_fields = ["created_at", "telegram_id"]
    ordering = ["-created_at"]
    search_fields = ["phone", "telegram_id"]

    SAFE_ACTIONS = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.SAFE_ACTIONS:
            return [IsAuthenticated(), IsAdminOrHigher()]
        # All write actions are restricted to Super Admin.
        return [IsAuthenticated(), IsSuperAdmin()]

    def get_queryset(self):
        from django.db.models import Q

        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        is_active = self.request.query_params.get("is_active")
        free_for_cleaning = self.request.query_params.get("free_for_cleaning")
        branch = self.request.query_params.get("branch")

        # Branch filter — surfaces every account whose role profile lives in
        # that branch. CEO (Super Admin) accounts have no branch by design;
        # they are always included so the operator never loses the CEO row
        # when narrowing down a branch.
        if branch:
            try:
                branch_id = int(branch)
            except (TypeError, ValueError):
                branch_id = None
            if branch_id is not None:
                qs = qs.filter(
                    Q(staff_profile__branch_id=branch_id)
                    | Q(administrator_profile__branch_id=branch_id)
                    | Q(director_profile__branch_id=branch_id)
                    | Q(superadmin_profile__isnull=False)
                )

        role_filters = {
            "superadmin": "superadmin_profile__isnull",
            "director": "director_profile__isnull",
            "administrator": "administrator_profile__isnull",
            "staff": "staff_profile__isnull",
            "client": "client_profile__isnull",
        }
        if role in role_filters:
            qs = qs.filter(**{role_filters[role]: False})

        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))

        # Exclude staff currently busy on a non-completed cleaning task.
        # Mirrors the rooms `?has_active_cleaning=false` UX so the form can
        # simply omit busy staff instead of showing a 400 after submit.
        if free_for_cleaning == "true":
            from apps.cleaning.models import CleaningTask  # local import to avoid cycle

            busy_staff_ids = (
                CleaningTask.objects
                .exclude(status=CleaningTask.TaskStatus.COMPLETED)
                .exclude(assigned_to__isnull=True)
                .values_list("assigned_to_id", flat=True)
            )
            qs = qs.exclude(staff_profile__in=list(busy_staff_ids))

        return qs

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        """Soft-disable an account (`is_active=False`)."""
        account = self.get_object()
        if account == request.user:
            return Response(
                {"detail": "You cannot disable your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        before = self._audit_snapshot(account)
        account.is_active = False
        account.save(update_fields=["is_active", "updated_at"])
        
        # Cleanup: unassign from active cleaning tasks
        if account.is_staff_member():
            from apps.cleaning.models import CleaningTask
            CleaningTask.objects.filter(
                assigned_to=account.staff_profile,
                status__in=["pending", "in_progress", "ai_checking", "retry_required"]
            ).update(assigned_to=None)
        
        # Cleanup: delete associated shift assignments
        from apps.staff.models import ShiftAssignment
        ShiftAssignment.objects.filter(account=account).delete()
        
        # Cleanup: delete associated cash sessions
        if account.is_administrator():
            from apps.admin_panel.models import CashSession
            CashSession.objects.filter(admin=account.administrator_profile).delete()
        
        self._audit_log(
            verb="disabled",
            entity_id=account.pk,
            before=before,
            after=self._audit_snapshot(account),
        )
        return Response(self.get_serializer(account).data)

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        """Re-enable a previously disabled account."""
        account = self.get_object()
        before = self._audit_snapshot(account)
        account.is_active = True
        account.save(update_fields=["is_active", "updated_at"])
        self._audit_log(
            verb="enabled",
            entity_id=account.pk,
            before=before,
            after=self._audit_snapshot(account),
        )
        return Response(self.get_serializer(account).data)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError("You cannot delete your own account.")
        
        # Cleanup: unassign from active cleaning tasks
        if instance.is_staff_member():
            from apps.cleaning.models import CleaningTask
            CleaningTask.objects.filter(
                assigned_to=instance.staff_profile,
                status__in=["pending", "in_progress", "ai_checking", "retry_required"]
            ).update(assigned_to=None)
        
        # Cleanup: delete associated shift assignments
        from apps.staff.models import ShiftAssignment
        ShiftAssignment.objects.filter(account=instance).delete()
        
        # Cleanup: delete associated cash sessions
        if instance.is_administrator():
            from apps.admin_panel.models import CashSession
            CashSession.objects.filter(admin=instance.administrator_profile).delete()
        
        # Defer to mixin so the deletion is audited.
        super().perform_destroy(instance)

    @action(
        detail=False,
        methods=["get"],
        url_path="branches-available-for-director",
    )
    def branches_available_for_director(self, request):
        """List branches that don't currently have an active Director.

        Used by the Super Admin user-creation modal to filter the branch
        dropdown when the chosen role is "director" — since each branch can
        have at most one active Director (April 2026 refactor).
        """
        taken_ids = set(
            Director.objects.filter(is_active=True).values_list("branch_id", flat=True)
        )
        branches = (
            Branch.objects.filter(is_active=True)
            .exclude(id__in=taken_ids)
            .order_by("name")
        )
        data = [{"id": b.id, "name": b.name} for b in branches]
        return Response(data)
