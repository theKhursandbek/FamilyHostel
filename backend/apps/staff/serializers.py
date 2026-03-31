"""Staff serializers (README Section 14.6)."""

import datetime

from rest_framework import serializers

from .models import Attendance, ShiftAssignment


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
