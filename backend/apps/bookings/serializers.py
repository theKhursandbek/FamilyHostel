"""Bookings serializers (README Section 14.4)."""

from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(
        source="client.full_name", read_only=True,
    )
    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "client",
            "client_name",
            "room",
            "room_number",
            "branch",
            "branch_name",
            "check_in_date",
            "check_out_date",
            "price_at_booking",
            "discount_amount",
            "final_price",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "final_price",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        check_in = attrs.get("check_in_date")
        check_out = attrs.get("check_out_date")
        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError(
                {"check_out_date": "Check-out date must be after check-in date."}
            )

        price = attrs.get("price_at_booking")
        if price is not None and price <= 0:
            raise serializers.ValidationError(
                {"price_at_booking": "Price must be greater than zero."}
            )

        discount = attrs.get("discount_amount", 0) or 0
        if discount < 0:
            raise serializers.ValidationError(
                {"discount_amount": "Discount cannot be negative."}
            )
        if price is not None and discount >= price:
            raise serializers.ValidationError(
                {"discount_amount": "Discount must be less than the booking price."}
            )

        return attrs


class BookingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    client_name = serializers.CharField(
        source="client.full_name", read_only=True,
    )
    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "client_name",
            "room_number",
            "check_in_date",
            "check_out_date",
            "final_price",
            "status",
            "created_at",
        ]
        read_only_fields = fields
