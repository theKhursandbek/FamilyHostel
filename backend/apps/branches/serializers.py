"""
Branches serializers.

Serializers for Branch, RoomType, Room, RoomImage (README Section 14.3).
"""

from rest_framework import serializers

from .models import Branch, Room, RoomImage, RoomType


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "location",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ["id", "name"]
        read_only_fields = ["id"]


class RoomImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomImage
        fields = ["id", "room", "image_url", "is_primary", "display_order", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


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
        ]
        read_only_fields = ["id", "status"]
