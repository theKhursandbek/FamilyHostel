"""
CEO (SuperAdmin) management endpoints.

Implements README §3.1 SuperAdmin permissions that previously had no UI:

    * Set salary system (shift rate, per-room rate, salary mode/cycle)
    * Set income % rules
    * Override any operation (logged in audit_logs)

URL prefix: /api/v1/admin-panel/

Endpoints:
    GET  /system-settings/             — current global settings (singleton)
    PUT  /system-settings/             — update salary mode/cycle/rates
    PATCH /system-settings/            — partial update

    GET  /income-rules/                — list rules (filter ?branch=)
    POST /income-rules/                — create
    PATCH /income-rules/{id}/          — update
    DELETE /income-rules/{id}/         — delete

    POST /overrides/                   — perform a logged override action
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Administrator, Director, Staff
from apps.accounts.permissions import IsSuperAdmin
from apps.payments.models import IncomeRule
from apps.payments.serializers import IncomeRuleSerializer
from apps.reports.models import AuditLog

from .models import SystemSettings


# ==============================================================================
# SYSTEM SETTINGS  (singleton)
# ==============================================================================


class SystemSettingsSerializer(serializers.ModelSerializer):
    """
    Phase 2 (REFACTOR_PLAN_2026_04 §5.1): the canonical staff per-shift rate
    is now ``staff_shift_rate``. The legacy ``shift_rate`` column is still
    exposed (read+write) for one release so older clients continue to work;
    when both are sent in the same payload, ``staff_shift_rate`` wins.
    """

    class Meta:
        model = SystemSettings
        fields = [
            "id",
            "salary_mode",
            "salary_cycle",
            "shift_rate",          # DEPRECATED — use staff_shift_rate
            "staff_shift_rate",
            "per_room_rate",
            "director_fixed_salary",
            "admin_shift_rate",
        ]
        read_only_fields = ["id"]

    def validate_staff_shift_rate(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Shift rate cannot be negative.")
        if value is not None and value > 99_999_999:
            raise serializers.ValidationError("Shift rate is unrealistically large.")
        return value

    def validate_per_room_rate(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Per-room rate cannot be negative.")
        if value is not None and value > 99_999_999:
            raise serializers.ValidationError("Per-room rate is unrealistically large.")
        return value

    def validate_director_fixed_salary(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Director salary cannot be negative.")
        if value is not None and value > 999_999_999:
            raise serializers.ValidationError("Director salary is unrealistically large.")
        return value

    def validate_admin_shift_rate(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Admin shift rate cannot be negative.")
        if value is not None and value > 99_999_999:
            raise serializers.ValidationError("Admin shift rate is unrealistically large.")
        return value

    def validate_salary_mode(self, value):
        allowed = {"shift", "per_room"}
        if value not in allowed:
            raise serializers.ValidationError(f"Must be one of: {', '.join(allowed)}.")
        return value

    def update(self, instance, validated_data):
        # Mirror legacy `shift_rate` writes onto the new `staff_shift_rate`
        # column when the new field was not explicitly provided.
        if (
            "staff_shift_rate" not in validated_data
            and "shift_rate" in validated_data
        ):
            validated_data["staff_shift_rate"] = validated_data["shift_rate"]
        return super().update(instance, validated_data)


def _get_or_create_settings() -> SystemSettings:
    """Return the singleton ``SystemSettings`` row, creating it if missing."""
    obj = SystemSettings.objects.order_by("pk").first()
    if obj is None:
        obj = SystemSettings.objects.create()
    return obj


class SystemSettingsView(APIView):
    """Singleton settings endpoint — only one row exists in the DB."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        obj = _get_or_create_settings()
        return Response(SystemSettingsSerializer(obj).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, *, partial: bool):
        obj = _get_or_create_settings()
        serializer = SystemSettingsSerializer(obj, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        before = SystemSettingsSerializer(obj).data
        serializer.save()
        after = SystemSettingsSerializer(obj).data

        AuditLog.objects.create(
            account=request.user,
            role="superadmin",
            action="update_system_settings",
            entity_type="SystemSettings",
            entity_id=obj.pk,
            before_data=before,
            after_data=after,
        )
        return Response(after)


# ==============================================================================
# INCOME RULES CRUD
# ==============================================================================


class IncomeRuleViewSet(viewsets.ModelViewSet):
    """
    Income percentage rules (README §14.7) — managed by CEO only.

    Filters: ``?branch=``
    """

    queryset = IncomeRule.objects.select_related("branch").all()
    serializer_class = IncomeRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["branch"]
    ordering_fields = ["branch", "min_income", "percent"]
    ordering = ["branch", "min_income"]

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(
            account=self.request.user,
            role="superadmin",
            action="create_income_rule",
            entity_type="IncomeRule",
            entity_id=instance.pk,
            before_data=None,
            after_data=IncomeRuleSerializer(instance).data,
        )

    def perform_update(self, serializer):
        before = IncomeRuleSerializer(serializer.instance).data
        instance = serializer.save()
        AuditLog.objects.create(
            account=self.request.user,
            role="superadmin",
            action="update_income_rule",
            entity_type="IncomeRule",
            entity_id=instance.pk,
            before_data=before,
            after_data=IncomeRuleSerializer(instance).data,
        )

    def perform_destroy(self, instance):
        before = IncomeRuleSerializer(instance).data
        pk = instance.pk
        instance.delete()
        AuditLog.objects.create(
            account=self.request.user,
            role="superadmin",
            action="delete_income_rule",
            entity_type="IncomeRule",
            entity_id=pk,
            before_data=before,
            after_data=None,
        )


# ==============================================================================
# PER-PERSON SALARY OVERRIDES
# ==============================================================================


_ROLE_REGISTRY = {
    "director": {
        "model": Director,
        "field": "salary_override",  # Phase 2: Director uses nullable override.
        "default_attr": "director_fixed_salary",
        "nullable": True,
    },
    "administrator": {
        "model": Administrator,
        "field": "salary_override",
        "default_attr": "admin_shift_rate",
        "nullable": True,
    },
    "staff": {
        "model": Staff,
        "field": "salary_override",
        "default_attr": "staff_shift_rate",  # informational; staff has shift + per-room
        "nullable": True,
    },
}


def _serialize_person(person, role: str, settings_obj: SystemSettings) -> dict:
    spec = _ROLE_REGISTRY[role]
    field = spec["field"]
    raw_value = getattr(person, field)
    # Staff: use per_room_rate when salary_mode is per_room, otherwise shift rate.
    if role == "staff" and getattr(settings_obj, "salary_mode", None) == "per_room":
        default_value = settings_obj.per_room_rate
    else:
        default_value = getattr(settings_obj, spec["default_attr"])

    if spec["nullable"]:
        is_custom = raw_value is not None
        effective = raw_value if is_custom else default_value
    else:
        # Director: any value different from the system default counts as custom.
        is_custom = raw_value is not None and Decimal(raw_value) != Decimal(default_value)
        effective = raw_value

    return {
        "id": person.pk,
        "full_name": person.full_name,
        "branch_id": person.branch_id,
        "branch_name": getattr(person.branch, "name", None),
        "salary_override": str(raw_value) if raw_value is not None else None,
        "effective_salary": str(effective) if effective is not None else None,
        "is_custom": is_custom,
        "default_salary": str(default_value) if default_value is not None else None,
    }


class RolePeopleView(APIView):
    """
    List people in a given role with their salary configuration.

    GET  /role-people/<role>/                 — list (?active=1 to filter)
    PATCH /role-people/<role>/<pk>/           — body: {"salary_override": "200000" | null}
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def _spec(self, role: str):
        spec = _ROLE_REGISTRY.get(role)
        if spec is None:
            return None
        return spec

    def get(self, request, role: str):
        spec = self._spec(role)
        if spec is None:
            return Response(
                {"detail": f"Unknown role '{role}'."},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = spec["model"].objects.select_related("branch").all()
        active = request.query_params.get("active")
        if active in {"1", "true", "True"}:
            qs = qs.filter(is_active=True)
        branch = request.query_params.get("branch")
        if branch:
            try:
                qs = qs.filter(branch_id=int(branch))
            except (TypeError, ValueError):
                pass

        qs = qs.order_by("full_name")
        settings_obj = _get_or_create_settings()
        data = [_serialize_person(p, role, settings_obj) for p in qs]
        return Response(data)

    @transaction.atomic
    def patch(self, request, role: str, pk: int):
        spec = self._spec(role)
        if spec is None:
            return Response(
                {"detail": f"Unknown role '{role}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            person = spec["model"].objects.select_for_update().select_related("branch").get(pk=pk)
        except spec["model"].DoesNotExist:
            return Response(
                {"detail": f"{role} #{pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if "salary_override" not in request.data:
            return Response(
                {"salary_override": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw = request.data.get("salary_override")
        field = spec["field"]
        settings_obj = _get_or_create_settings()

        if raw in (None, "", "null"):
            if spec["nullable"]:
                new_value = None
            else:
                # Director: reset means restore the system default.
                new_value = Decimal(getattr(settings_obj, spec["default_attr"]))
        else:
            try:
                new_value = Decimal(str(raw))
            except (ArithmeticError, ValueError):
                return Response(
                    {"salary_override": "Must be a valid decimal."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if new_value < 0:
                return Response(
                    {"salary_override": "Salary cannot be negative."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        before = _serialize_person(person, role, settings_obj)
        setattr(person, field, new_value)
        person.save(update_fields=[field])
        after = _serialize_person(person, role, settings_obj)

        AuditLog.objects.create(
            account=request.user,
            role="superadmin",
            action=f"set_salary:{role}",
            entity_type=spec["model"].__name__,
            entity_id=person.pk,
            before_data=before,
            after_data=after,
        )

        return Response(after)
