"""Cleaning serializers (README Section 14.5)."""

from rest_framework import serializers

from .models import AIResult, CleaningImage, CleaningTask


class CleaningImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CleaningImage
        fields = ["id", "task", "image", "image_url", "zone", "is_purged", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at", "image_url", "zone", "is_purged"]
        extra_kwargs = {"image": {"write_only": True}}

    def get_image_url(self, obj: CleaningImage) -> str | None:
        if obj.is_purged:
            return None
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CleaningImageUploadSerializer(serializers.Serializer):
    """Validates a camera submission: one image per zone.

    Staff must supply all four required zones (bed, bathroom, floor, trash);
    an optional fifth ``extra`` image is allowed for damage/issue reporting.
    ``images`` and ``zones`` are parallel lists of equal length.
    """

    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=len(CleaningImage.REQUIRED_ZONES),
        max_length=len(CleaningImage.REQUIRED_ZONES) + 1,
        help_text="Camera photos, one per zone (4 required + 1 optional extra).",
    )
    zones = serializers.ListField(
        child=serializers.ChoiceField(choices=CleaningImage.Zone.choices),
        min_length=len(CleaningImage.REQUIRED_ZONES),
        max_length=len(CleaningImage.REQUIRED_ZONES) + 1,
        help_text="Zone label for each image (same order/length as images).",
    )

    def validate(self, attrs):
        images = attrs["images"]
        zones = attrs["zones"]
        if len(images) != len(zones):
            raise serializers.ValidationError(
                {"zones": "Each image must have a matching zone label."}
            )
        if len(set(zones)) != len(zones):
            raise serializers.ValidationError(
                {"zones": "Each zone may only be submitted once."}
            )
        missing = set(CleaningImage.REQUIRED_ZONES) - set(zones)
        if missing:
            raise serializers.ValidationError(
                {"zones": f"Missing required zone photo(s): {', '.join(sorted(missing))}."}
            )
        return attrs


class AIResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResult
        fields = [
            "id",
            "task",
            "result",
            "feedback_text",
            "zones",
            "confidence",
            "failure_reason",
            "ai_model_version",
            "created_at",
        ]
        read_only_fields = fields


class OverrideSerializer(serializers.Serializer):
    """Serializer for the supervisor "Mark Cleaned" (override) endpoint.

    The reason is OPTIONAL — Administrators, Directors and Super Admins may
    mark a room cleaned without justification, even over a negative AI verdict.
    """

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Optional note for overriding the AI result.",
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
    """Lightweight serializer for list views.

    Includes the per-task ``ai_results`` (latest verdict + per-zone breakdown)
    and the ``completed_at`` / ``updated_at`` timestamps so the staff dashboard
    card can render retry feedback and the "rooms cleaned this week" stat
    without a second round-trip. The viewset already prefetches ``ai_results``
    so this stays a single query.
    """

    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name", read_only=True, default=None,
    )
    ai_results = AIResultSerializer(many=True, read_only=True)

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
            "ai_results",
            "completed_at",
            "updated_at",
            "created_at",
        ]
        read_only_fields = fields
