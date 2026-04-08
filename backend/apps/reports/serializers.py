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
    """Validates input for creating a penalty."""

    account = serializers.IntegerField()
    type = serializers.ChoiceField(choices=Penalty.PenaltyType.choices)
    count = serializers.IntegerField(min_value=1, required=False, default=1)
    penalty_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(required=False, default="", allow_blank=True)


class UpdatePenaltySerializer(serializers.Serializer):
    """Validates input for updating a penalty (PATCH)."""

    type = serializers.ChoiceField(
        choices=Penalty.PenaltyType.choices, required=False,
    )
    count = serializers.IntegerField(min_value=1, required=False)
    penalty_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
    )
    reason = serializers.CharField(required=False, allow_blank=True)


# ==============================================================================
# FACILITY LOG
# ==============================================================================


class FacilityLogSerializer(serializers.ModelSerializer):
    """Read-only representation of a facility log."""

    class Meta:
        model = FacilityLog
        fields = [
            "id",
            "branch",
            "type",
            "description",
            "cost",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreateFacilityLogSerializer(serializers.Serializer):
    """Validates input for creating a facility log."""

    branch = serializers.IntegerField(required=False)
    type = serializers.ChoiceField(choices=FacilityLog.FacilityType.choices)
    description = serializers.CharField()
    cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=None,
    )


class UpdateFacilityLogSerializer(serializers.Serializer):
    """Validates input for updating a facility log (PATCH)."""

    type = serializers.ChoiceField(
        choices=FacilityLog.FacilityType.choices, required=False,
    )
    description = serializers.CharField(required=False)
    cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False,
    )
    status = serializers.ChoiceField(
        choices=FacilityLog.LogStatus.choices, required=False,
    )


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
