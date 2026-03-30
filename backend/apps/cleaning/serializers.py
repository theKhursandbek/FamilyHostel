"""Cleaning serializers (README Section 14.5)."""

from rest_framework import serializers

from .models import AIResult, CleaningImage, CleaningTask


class CleaningImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleaningImage
        fields = ["id", "task", "image_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class AIResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResult
        fields = [
            "id",
            "task",
            "result",
            "feedback_text",
            "ai_model_version",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CleaningTaskSerializer(serializers.ModelSerializer):
    images = CleaningImageSerializer(many=True, read_only=True)
    ai_results = AIResultSerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name", read_only=True, default=None,
    )
    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )

    class Meta:
        model = CleaningTask
        fields = [
            "id",
            "room",
            "room_number",
            "branch",
            "status",
            "priority",
            "assigned_to",
            "assigned_to_name",
            "images",
            "ai_results",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class CleaningTaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name", read_only=True, default=None,
    )

    class Meta:
        model = CleaningTask
        fields = [
            "id",
            "room_number",
            "branch",
            "status",
            "priority",
            "assigned_to_name",
            "created_at",
        ]
        read_only_fields = fields
