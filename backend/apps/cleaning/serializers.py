"""Cleaning serializers (README Section 14.5)."""

from rest_framework import serializers

from .models import AIResult, CleaningImage, CleaningTask


class CleaningImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CleaningImage
        fields = ["id", "task", "image", "image_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at", "image_url"]
        extra_kwargs = {"image": {"write_only": True}}

    def get_image_url(self, obj: CleaningImage) -> str | None:
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CleaningImageUploadSerializer(serializers.Serializer):
    """Serializer for the image upload endpoint."""

    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=10,
        help_text="Upload 1–10 cleaning verification images.",
    )


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


class OverrideSerializer(serializers.Serializer):
    """Serializer for the Director override endpoint."""

    reason = serializers.CharField(
        required=True,
        min_length=5,
        max_length=500,
        help_text="Reason for overriding the AI result.",
    )


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
            "retry_count",
            "override_reason",
            "overridden_by",
            "images",
            "ai_results",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "retry_count",
            "override_reason",
            "overridden_by",
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
            "retry_count",
            "created_at",
        ]
        read_only_fields = fields
