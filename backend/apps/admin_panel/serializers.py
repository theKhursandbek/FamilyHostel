"""
Admin Panel serializers — Room Inspections & Cash Sessions (Step 21.6).
"""

from rest_framework import serializers

from .models import CashSession, RoomInspection, RoomInspectionImage


# ==============================================================================
# ROOM INSPECTION
# ==============================================================================


class RoomInspectionImageSerializer(serializers.ModelSerializer):
    """Read-only representation of an inspection photo."""

    class Meta:
        model = RoomInspectionImage
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = fields


class RoomInspectionSerializer(serializers.ModelSerializer):
    """Read-only representation of a room inspection."""

    images = RoomInspectionImageSerializer(many=True, read_only=True)

    class Meta:
        model = RoomInspection
        fields = [
            "id",
            "room",
            "branch",
            "inspected_by",
            "booking",
            "status",
            "notes",
            "created_at",
            "images",
        ]
        read_only_fields = fields


class CreateRoomInspectionSerializer(serializers.Serializer):
    """Validates input for creating a room inspection."""

    room = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=RoomInspection.InspectionStatus.choices,
    )
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    booking = serializers.IntegerField(required=False, allow_null=True, default=None)


# ==============================================================================
# CASH SESSION
# ==============================================================================


class CashSessionSerializer(serializers.ModelSerializer):
    """Read-only representation of a cash session."""

    class Meta:
        model = CashSession
        fields = [
            "id",
            "admin",
            "branch",
            "shift_type",
            "start_time",
            "end_time",
            "opening_balance",
            "closing_balance",
            "difference",
            "note",
            "handed_over_to",
            "updated_at",
        ]
        read_only_fields = fields


class OpenCashSessionSerializer(serializers.Serializer):
    """Validates input for opening a cash session."""

    shift_type = serializers.ChoiceField(choices=CashSession.ShiftType.choices)
    opening_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    note = serializers.CharField(required=False, default="", allow_blank=True)


class CloseCashSessionSerializer(serializers.Serializer):
    """Validates input for closing a cash session."""

    closing_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    note = serializers.CharField(required=False, default="", allow_blank=True)


class HandoverCashSessionSerializer(serializers.Serializer):
    """Validates input for handing over a cash session."""

    handed_over_to = serializers.IntegerField()
    closing_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    note = serializers.CharField(required=False, default="", allow_blank=True)
