"""Staff serializers (README Section 14.6)."""

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
