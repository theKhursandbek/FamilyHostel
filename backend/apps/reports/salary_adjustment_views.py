"""
Salary Adjustment endpoints (REFACTOR_PLAN_2026_04 §3.7 / Q2 Option B).

Replaces the old per-month-row ``AdminMonthlyAdjustment`` API with a list +
modal CRUD. Each row is one explicit ``penalty`` or ``bonus_plus`` entry
with a free-form reason.

Targets: Q8 — only active **Administrators and Staff** are valid targets.
Directors and the CEO are never selectable.

Mounted under ``/api/v1/reports/salary-adjustments/``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Account, Administrator, Staff
from apps.branches.models import Branch

from .models import SalaryAdjustment
from .services import log_action


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


class SalaryAdjustmentSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalaryAdjustment
        fields = [
            "id",
            "account",
            "account_name",
            "role",
            "branch",
            "year",
            "month",
            "kind",
            "amount",
            "reason",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id", "account_name", "role",
            "created_by", "created_by_name", "created_at",
        ]

    def _profile_name(self, account):
        for attr in ("administrator_profile", "staff_profile",
                     "director_profile", "client_profile"):
            prof = getattr(account, attr, None)
            name = getattr(prof, "full_name", None) if prof else None
            if name:
                return name
        return getattr(account, "phone", None) or str(account)

    def get_account_name(self, obj):
        return self._profile_name(obj.account)

    def get_role(self, obj):
        if Administrator.objects.filter(account_id=obj.account_id).exists():
            return "administrator"
        if Staff.objects.filter(account_id=obj.account_id).exists():
            return "staff"
        return ""

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ""
        return self._profile_name(obj.created_by)

    def validate_reason(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Reason is required.")
        return value.strip()

    def validate_amount(self, value):
        try:
            v = Decimal(str(value))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError("Amount must be a decimal value.")
        if v <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return v


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------


def _user_branch_id(user):
    """Return the branch id this user belongs to (None for SuperAdmin)."""
    from apps.accounts.branch_scope import get_user_branch
    b = get_user_branch(user)
    return b.pk if b else None


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------


class SalaryAdjustmentViewSet(viewsets.ModelViewSet):
    """
    Salary adjustments — penalty / bonus_plus entries per (account, year, month).

    Permission matrix:
        - SuperAdmin (CEO): full access across every branch.
        - Director: full access on accounts in their own branch.
        - Administrator/Staff: read-only on their own rows (history).

    Filterable via ``?branch=&year=&month=&kind=&account=``.
    """

    serializer_class = SalaryAdjustmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = SalaryAdjustment.objects.select_related(
            "account", "branch", "created_by",
        ).all()
        user = self.request.user

        # Filters
        params = self.request.query_params
        if params.get("branch"):
            qs = qs.filter(branch_id=params["branch"])
        if params.get("year"):
            qs = qs.filter(year=params["year"])
        if params.get("month"):
            qs = qs.filter(month=params["month"])
        if params.get("kind"):
            qs = qs.filter(kind=params["kind"])
        if params.get("account"):
            qs = qs.filter(account_id=params["account"])

        # Scope by role
        if user.is_superadmin:
            return qs
        user_branch_id = _user_branch_id(user)
        if user.is_director:
            return qs.filter(branch_id=user_branch_id)
        # Admin/Staff: only their own rows
        return qs.filter(account=user)

    def _resolve_target(self, account_id):
        """Q8: target must be an active Administrator or Staff."""
        try:
            account = Account.objects.get(pk=account_id)
        except (Account.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({"account": "Account not found."})

        is_admin = Administrator.objects.filter(
            account_id=account.pk, is_active=True,
        ).exists()
        is_staff = Staff.objects.filter(
            account_id=account.pk, is_active=True,
        ).exists()
        if not (is_admin or is_staff):
            raise serializers.ValidationError({
                "account": (
                    "Salary adjustments can only target active Administrators "
                    "or Staff (REFACTOR_PLAN_2026_04 §3.7 / Q8)."
                ),
            })
        return account

    def _resolve_branch(self, account, requested_branch_id):
        """Director must operate within their own branch; CEO may pick any."""
        # Find the account's branch via its admin/staff profile.
        admin = Administrator.objects.filter(account_id=account.pk).first()
        staff = Staff.objects.filter(account_id=account.pk).first()
        target_branch_id = (admin and admin.branch_id) or (staff and staff.branch_id)
        if not target_branch_id:
            raise serializers.ValidationError({
                "account": "Target has no branch assignment.",
            })

        user = self.request.user
        if user.is_director:
            user_b = _user_branch_id(user)
            if target_branch_id != user_b:
                raise serializers.ValidationError({
                    "account": "Account is on a different branch.",
                })
        # If client supplied a branch, sanity-check it matches.
        if requested_branch_id and int(requested_branch_id) != target_branch_id:
            raise serializers.ValidationError({
                "branch": "Branch does not match the target account's branch.",
            })
        return Branch.objects.get(pk=target_branch_id)

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superadmin or user.is_director):
            return Response(
                {"detail": "Only Director or CEO can create salary adjustments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        account = self._resolve_target(request.data.get("account"))
        branch = self._resolve_branch(account, request.data.get("branch"))

        adjustment = SalaryAdjustment.objects.create(
            account=account,
            branch=branch,
            year=ser.validated_data["year"],
            month=ser.validated_data["month"],
            kind=ser.validated_data["kind"],
            amount=ser.validated_data["amount"],
            reason=ser.validated_data["reason"],
            created_by=user,
        )
        log_action(
            account=user,
            action=f"salary_adjustment.{adjustment.kind}_created",
            entity_type="SalaryAdjustment",
            entity_id=adjustment.pk,
            after_data={
                "target_account": account.pk,
                "branch": branch.pk,
                "year": adjustment.year,
                "month": adjustment.month,
                "kind": adjustment.kind,
                "amount": str(adjustment.amount),
                "reason": adjustment.reason,
            },
        )
        return Response(
            self.get_serializer(adjustment).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superadmin or user.is_director):
            return Response(
                {"detail": "Only Director or CEO can delete salary adjustments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        snapshot = {
            "target_account": instance.account_id,
            "branch": instance.branch_id,
            "year": instance.year,
            "month": instance.month,
            "kind": instance.kind,
            "amount": str(instance.amount),
            "reason": instance.reason,
        }
        adj_id = instance.pk
        kind = instance.kind
        instance.delete()
        log_action(
            account=user,
            action=f"salary_adjustment.{kind}_deleted",
            entity_type="SalaryAdjustment",
            entity_id=adj_id,
            before_data=snapshot,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="targets")
    def targets(self, request):
        """GET /reports/salary-adjustments/targets/?branch=<id>

        Q8 dropdown source — active Administrators + Staff for a branch.
        Director: pinned to own branch (ignores ?branch).
        CEO: ?branch=<id> required.
        """
        user = request.user
        if not (user.is_superadmin or user.is_director):
            return Response(
                {"detail": "Only Director or CEO can list adjustment targets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_director:
            branch_id = _user_branch_id(user)
        else:
            raw = request.query_params.get("branch")
            if not raw:
                return Response(
                    {"branch": "Required for SuperAdmin."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                branch_id = int(raw)
            except (TypeError, ValueError):
                return Response(
                    {"branch": "Must be an integer id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        accounts = (
            Account.objects
            .filter(
                Q(administrator_profile__branch_id=branch_id,
                  administrator_profile__is_active=True)
                | Q(staff_profile__branch_id=branch_id,
                    staff_profile__is_active=True),
            )
            .select_related("administrator_profile", "staff_profile")
            .distinct()
            .order_by("phone")
        )
        rows = []
        for acc in accounts:
            admin = getattr(acc, "administrator_profile", None)
            staff = getattr(acc, "staff_profile", None)
            full_name = (
                (admin and admin.full_name)
                or (staff and staff.full_name)
                or getattr(acc, "phone", "")
            )
            role = "administrator" if admin else "staff"
            rows.append({
                "account_id": acc.pk,
                "full_name": full_name,
                "role": role,
                "branch_id": branch_id,
            })
        return Response({"branch": branch_id, "results": rows})

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        """GET /reports/salary-adjustments/totals/?branch=&year=&month=

        Aggregated penalty/bonus_plus totals per account for a month.
        Used by the Salary page summary tiles.
        """
        params = request.query_params
        if not (params.get("branch") and params.get("year") and params.get("month")):
            return Response(
                {"detail": "branch, year, month are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = (
            self.get_queryset()
            .values("account_id", "kind")
            .annotate(total=Sum("amount"))
        )
        by_account: dict[int, dict[str, str]] = {}
        for row in qs:
            slot = by_account.setdefault(row["account_id"], {
                "penalty": "0", "bonus_plus": "0",
            })
            slot[row["kind"]] = str(row["total"] or Decimal("0"))
        return Response({"results": by_account})
