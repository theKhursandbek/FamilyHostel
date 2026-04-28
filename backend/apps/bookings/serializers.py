"""Bookings serializers (README Section 14.4)."""

from decimal import Decimal

from rest_framework import serializers

from .models import Booking


def _balance_fields(obj):
    """Return (paid_total, balance_due) Decimals for a booking instance."""
    from apps.payments.services import paid_total, balance_due
    return paid_total(obj), balance_due(obj)


class BookingSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(
        source="client.full_name", read_only=True,
    )
    client_phone = serializers.CharField(
        source="client.account.phone", read_only=True,
    )
    client_passport = serializers.CharField(
        source="client.passport_number", read_only=True,
    )
    room_number = serializers.CharField(
        source="room.room_number", read_only=True,
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True,
    )
    room_base_price = serializers.DecimalField(
        source="room.base_price", max_digits=12, decimal_places=2, read_only=True,
    )
    paid_total = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()

    def get_paid_total(self, obj):
        return str(_balance_fields(obj)[0])

    def get_balance_due(self, obj):
        return str(_balance_fields(obj)[1])

    class Meta:
        model = Booking
        fields = [
            "id",
            "client",
            "client_name",
            "client_phone",
            "client_passport",
            "room",
            "room_number",
            "room_base_price",
            "branch",
            "branch_name",
            "check_in_date",
            "check_out_date",
            "price_at_booking",
            "discount_amount",
            "final_price",
            "paid_total",
            "balance_due",
            "status",
            "source",
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
    branch_name = serializers.CharField(
        source="branch.name", read_only=True,
    )
    room_base_price = serializers.DecimalField(
        source="room.base_price", max_digits=12, decimal_places=2, read_only=True,
    )
    paid_total = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()

    def get_paid_total(self, obj):
        return str(_balance_fields(obj)[0])

    def get_balance_due(self, obj):
        return str(_balance_fields(obj)[1])

    class Meta:
        model = Booking
        fields = [
            "id",
            "client_name",
            "room",
            "room_number",
            "branch",
            "branch_name",
            "room_base_price",
            "check_in_date",
            "check_out_date",
            "price_at_booking",
            "discount_amount",
            "final_price",
            "paid_total",
            "balance_due",
            "status",
            "source",
            "created_at",
        ]
        read_only_fields = fields


class WalkInBookingSerializer(serializers.Serializer):
    """Input serializer for ``POST /bookings/walk-in/``.

    Validates the new-guest fields plus the booking fields.  All FK fields
    are passed by primary key; the view resolves them to objects before
    handing them to ``create_walkin_booking``.
    """

    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    passport_number = serializers.CharField(max_length=50)

    room = serializers.IntegerField(min_value=1)
    branch = serializers.IntegerField(min_value=1)
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    price_at_booking = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0,
    )

    def validate(self, attrs):
        if attrs["check_out_date"] <= attrs["check_in_date"]:
            raise serializers.ValidationError(
                {"check_out_date": "Check-out date must be after check-in date."}
            )
        price = attrs.get("price_at_booking")
        if price is not None and price <= 0:
            raise serializers.ValidationError(
                {"price_at_booking": "Price must be greater than zero."}
            )
        discount = attrs.get("discount_amount") or 0
        if discount < 0:
            raise serializers.ValidationError(
                {"discount_amount": "Discount cannot be negative."}
            )
        if price is not None and discount >= price:
            raise serializers.ValidationError(
                {"discount_amount": "Discount must be less than the booking price."}
            )
        return attrs


class ExtendBookingSerializer(serializers.Serializer):
    """Input serializer for ``POST /bookings/{pk}/extend/``."""

    new_check_out_date = serializers.DateField()
    additional_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
    )


class RefundSerializer(serializers.Serializer):
    """Input serializer for ``POST /bookings/{pk}/refund/``."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
    )
    reason = serializers.CharField(max_length=100, required=False, default="manual")


class CompleteBookingSerializer(serializers.Serializer):
    """Input serializer for ``POST /bookings/{pk}/complete/``."""

    refund_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        default=Decimal("0"),
    )
