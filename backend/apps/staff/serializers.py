"""Staff serializers (README Section 14.6 & Step 21.5)."""

import datetime

from rest_framework import serializers

from .models import Attendance, DayOffRequest, ShiftAssignment


# Hostel-wide shift windows (mirrors apps.staff.services.SHIFT_START_TIMES).
SHIFT_WINDOWS = {
    "day": ("08:00", "19:00"),
    "night": ("19:00", "08:00"),
}


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    shift_start_time = serializers.SerializerMethodField()
    shift_end_time = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "account",
            "account_name",
            "role",
            "branch",
            "branch_name",
            "shift_type",
            "shift_start_time",
            "shift_end_time",
            "date",
            "assigned_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "assigned_by",
            "account_name",
            "branch_name",
            "shift_start_time",
            "shift_end_time",
        ]

    def get_account_name(self, obj):
        acc = obj.account
        if acc is None:
            return None
        for attr in ("administrator_profile", "director_profile", "staff_profile"):
            prof = getattr(acc, attr, None)
            full = getattr(prof, "full_name", None) if prof else None
            if full:
                return full
        return getattr(acc, "phone", None) or f"#{acc.pk}"

    def get_branch_name(self, obj):
        return getattr(obj.branch, "name", None) or (f"Branch #{obj.branch_id}" if obj.branch_id else None)

    def get_shift_start_time(self, obj):
        return SHIFT_WINDOWS.get(obj.shift_type, (None, None))[0]

    def get_shift_end_time(self, obj):
        return SHIFT_WINDOWS.get(obj.shift_type, (None, None))[1]

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
