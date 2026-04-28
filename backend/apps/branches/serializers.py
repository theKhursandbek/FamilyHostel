"""
Branches serializers.

Serializers for Branch, RoomType, Room, RoomImage (README Section 14.3).
"""

from rest_framework import serializers

from .models import Branch, Room, RoomImage, RoomType


class BranchSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "location",
            "image",
            "image_url",
            "is_active",
            "working_days_per_month",
            "monthly_expense_limit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "created_at", "updated_at"]
        extra_kwargs = {"image": {"write_only": True, "required": False, "allow_null": True}}

    def get_image_url(self, obj: Branch) -> str | None:
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ["id", "name"]
        read_only_fields = ["id"]


class RoomImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = RoomImage
        fields = ["id", "room", "image", "image_url", "is_primary", "display_order", "uploaded_at"]
        read_only_fields = ["id", "image_url", "uploaded_at"]
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def get_image_url(self, obj: RoomImage) -> str | None:
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return obj.image_url or None


class RoomImageUploadSerializer(serializers.Serializer):
    """Multi-image upload payload for the Room images endpoint (max 3 total)."""

    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=RoomImage.MAX_IMAGES_PER_ROOM,
        help_text=(
            f"Upload 1–{RoomImage.MAX_IMAGES_PER_ROOM} room photos. "
            f"Total photos per room is capped at {RoomImage.MAX_IMAGES_PER_ROOM}."
        ),
    )


class RoomSerializer(serializers.ModelSerializer):
    images = RoomImageSerializer(many=True, read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Room
        fields = [
            "id",
            "branch",
            "branch_name",
            "room_type",
            "room_type_name",
            "room_number",
            "base_price",
            "status",
            "is_active",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_room_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Room number cannot be blank.")
        return value.strip()


class RoomListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views (no nested images)."""

    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    primary_image_url = serializers.SerializerMethodField()
    images = RoomImageSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = [
            "id",
            "branch",
            "branch_name",
            "room_type",
            "room_type_name",
            "room_number",
            "status",
            "is_active",
            "primary_image_url",
            "images",
            "base_price",
        ]
        read_only_fields = ["id", "status", "primary_image_url", "images"]

    def get_primary_image_url(self, obj):
        first = obj.images.all().first() if hasattr(obj, "images") else None
        if not first:
            return None
        request = self.context.get("request")
        if first.image and hasattr(first.image, "url"):
            return request.build_absolute_uri(first.image.url) if request else first.image.url
        return first.image_url or None
