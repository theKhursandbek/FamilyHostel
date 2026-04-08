"""Staff serializers (README Section 14.6 & Step 21.5)."""

import datetime

from rest_framework import serializers

from .models import Attendance, DayOffRequest, ShiftAssignment


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "account",
            "role",
            "branch",
            "shift_type",
            "date",
            "assigned_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_date(self, value):
        if value < datetime.date.today():
            raise serializers.ValidationError("Shift date cannot be in the past.")
        return value


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = [
            "id",
            "account",
            "branch",
            "date",
            "shift_type",
            "check_in",
            "check_out",
            "status",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "updated_at"]


# ==============================================================================
# DAY-OFF REQUEST SERIALIZERS (Step 21.5)
# ==============================================================================


class DayOffRequestSerializer(serializers.ModelSerializer):
    """Read-only representation of a day-off request."""

    class Meta:
        model = DayOffRequest
        fields = [
            "id",
            "account",
            "branch",
            "start_date",
            "end_date",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_comment",
            "created_at",
        ]
        read_only_fields = fields


class CreateDayOffRequestSerializer(serializers.Serializer):
    """Validates input for creating a day-off request."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, default="", allow_blank=True)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."},
            )
        if attrs["start_date"] < datetime.date.today():
            raise serializers.ValidationError(
                {"start_date": "Start date cannot be in the past."},
            )
        return attrs


class ReviewDayOffRequestSerializer(serializers.Serializer):
    """Validates input for approve / reject actions."""

    comment = serializers.CharField(required=False, default="", allow_blank=True)
