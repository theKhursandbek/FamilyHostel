"""
Reports serializers — Penalties, Facility Logs & Monthly Reports (Step 21.7).
"""

from __future__ import annotations

import json

from rest_framework import serializers

from .models import FacilityLog, MonthlyReport, Penalty


# ==============================================================================
# PENALTY
# ==============================================================================


class PenaltySerializer(serializers.ModelSerializer):
    """Read-only representation of a penalty."""

    class Meta:
        model = Penalty
        fields = [
            "id",
            "account",
            "type",
            "count",
            "penalty_amount",
            "reason",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreatePenaltySerializer(serializers.Serializer):
    """Validates input for creating a penalty.

    Per REFACTOR_PLAN_2026_04 §2.1:
      - ``type`` is OPTIONAL (free-form penalties may have no category).
      - ``reason`` is REQUIRED and must be non-empty (after .strip()).
    """

    account = serializers.IntegerField()
    type = serializers.ChoiceField(
        choices=Penalty.PenaltyType.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    count = serializers.IntegerField(min_value=1, required=False, default=1)
    penalty_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(required=True, allow_blank=False)

    def validate_reason(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Reason is required.")
        return cleaned

    def validate_type(self, value):
        # Normalise empty string → None so it can be saved on the nullable column.
        return value or None


class UpdatePenaltySerializer(serializers.Serializer):
    """Validates input for updating a penalty (PATCH).

    Same Phase-3 rules as creation: ``type`` optional, ``reason`` (when sent)
    must be non-empty.
    """

    type = serializers.ChoiceField(
        choices=Penalty.PenaltyType.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    count = serializers.IntegerField(min_value=1, required=False)
    penalty_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
    )
    reason = serializers.CharField(required=False, allow_blank=False)

    def validate_reason(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Reason is required.")
        return cleaned

    def validate_type(self, value):
        return value or None


# ==============================================================================
# FACILITY LOG
# ==============================================================================


class FacilityLogSerializer(serializers.ModelSerializer):
    """Read-only representation of a facility log / expense request."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FacilityLog
        fields = [
            "id",
            "branch",
            "branch_name",
            "type",
            "shift_type",
            "description",
            "cost",
            "status",
            "payment_method",
            "requested_by",
            "requested_by_name",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "approval_note",
            "rejected_by",
            "rejected_by_name",
            "rejected_at",
            "rejection_reason",
            "over_limit_justified",
            "over_limit_reason",
            "paid_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        acc = obj.requested_by
        return getattr(acc, "phone", None) if acc else None

    def get_approved_by_name(self, obj):
        sa = obj.approved_by
        return getattr(sa, "full_name", None) if sa else None

    def get_rejected_by_name(self, obj):
        sa = obj.rejected_by
        return getattr(sa, "full_name", None) if sa else None


class CreateFacilityLogSerializer(serializers.Serializer):
    """Validates input for filing a new expense request."""

    branch = serializers.IntegerField(required=False)
    type = serializers.ChoiceField(choices=FacilityLog.FacilityType.choices)
    shift_type = serializers.ChoiceField(
        choices=FacilityLog.ShiftType.choices, required=False, allow_null=True,
    )
    description = serializers.CharField()
    cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=None,
    )


class UpdateFacilityLogSerializer(serializers.Serializer):
    """Validates input for updating a facility log (PATCH)."""

    type = serializers.ChoiceField(
        choices=FacilityLog.FacilityType.choices, required=False,
    )
    shift_type = serializers.ChoiceField(
        choices=FacilityLog.ShiftType.choices, required=False, allow_null=True,
    )
    description = serializers.CharField(required=False)
    cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False,
    )
    status = serializers.ChoiceField(
        choices=FacilityLog.LogStatus.choices, required=False,
    )


class ApproveExpenseSerializer(serializers.Serializer):
    """CEO approve payload (REFACTOR_PLAN_2026_04 §7.3)."""

    payment_method = serializers.ChoiceField(
        choices=FacilityLog.PaymentMethod.choices,
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")
    over_limit_justified = serializers.BooleanField(required=False, default=False)
    over_limit_reason = serializers.CharField(
        required=False, allow_blank=True, default="",
    )


class RejectExpenseSerializer(serializers.Serializer):
    """CEO reject payload."""

    reason = serializers.CharField()


# ==============================================================================
# MONTHLY REPORT
# ==============================================================================


class MonthlyReportSerializer(serializers.ModelSerializer):
    """Read-only representation of a monthly report."""

    summary_data = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyReport
        fields = [
            "id",
            "branch",
            "month",
            "year",
            "created_by",
            "summary_notes",
            "summary_data",
            "created_at",
        ]
        read_only_fields = fields

    def get_summary_data(self, obj: MonthlyReport) -> dict | None:
        """Parse the JSON stored in summary_notes."""
        if obj.summary_notes:
            try:
                return json.loads(obj.summary_notes)
            except (json.JSONDecodeError, TypeError):
                return None
        return None


class GenerateReportSerializer(serializers.Serializer):
    """Validates input for generating a monthly report."""

    month = serializers.IntegerField(min_value=1, max_value=12)
    year = serializers.IntegerField(min_value=2020, max_value=2100)
