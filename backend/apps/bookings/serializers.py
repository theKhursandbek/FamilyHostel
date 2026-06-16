"""Bookings serializers (README Section 14.4)."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.common.validators import (
    validate_dob,
    validate_full_name,
    validate_passport,
    validate_uz_phone,
)

from .models import Booking, BookingExtension

# How the cash actually moved. Mirrors apps.payments.models.PaymentMethod —
# declared inline to avoid importing the payments app at module load.
PAYMENT_METHOD_CHOICES = (
    ("cash", "Cash"),
    ("terminal", "Terminal (POS)"),
    ("qr", "QR Code"),
    ("card_transfer", "Transfer to Card"),
)


def _balance_fields(obj):
    """Return (paid_total, balance_due) Decimals for a booking instance."""
    from apps.payments.services import paid_total, balance_due
    return paid_total(obj), balance_due(obj)


def _active_extensions(obj):
    """Active extension rows for a booking (uses prefetch when available)."""
    return [
        e for e in obj.extensions.all()
        if e.status == BookingExtension.ExtensionStatus.ACTIVE
    ]


class BookingExtensionSerializer(serializers.ModelSerializer):
    """Read-only nested representation of a single extension segment."""

    created_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        acc = obj.created_by
        if not acc:
            return None
        for attr in (
            "director_profile",
            "administrator_profile",
            "superadmin_profile",
            "staff_profile",
        ):
            prof = getattr(acc, attr, None)
            name = getattr(prof, "full_name", None) if prof else None
            if name:
                return name
        return getattr(acc, "phone", None) or str(acc)

    class Meta:
        model = BookingExtension
        fields = [
            "id",
            "previous_check_out_date",
            "new_check_out_date",
            "additional_price",
            "status",
            "created_by_name",
            "created_at",
            "canceled_at",
        ]
        read_only_fields = fields


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
    room_primary_image_url = serializers.SerializerMethodField()
    room_image_urls = serializers.SerializerMethodField()
    paid_total = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()
    client_dob = serializers.DateField(
        source="client.date_of_birth", read_only=True,
    )
    extensions = BookingExtensionSerializer(many=True, read_only=True)
    has_active_extension = serializers.SerializerMethodField()
    can_cancel_extension = serializers.SerializerMethodField()

    def get_paid_total(self, obj):
        return str(_balance_fields(obj)[0])

    def get_balance_due(self, obj):
        return str(_balance_fields(obj)[1])

    def get_has_active_extension(self, obj):
        return bool(_active_extensions(obj))

    def get_can_cancel_extension(self, obj):
        return bool(_active_extensions(obj)) and obj.status in (
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.PAID,
        )

    def _abs_image_url(self, img):
        request = self.context.get("request")
        if getattr(img, "image", None) and hasattr(img.image, "url"):
            return request.build_absolute_uri(img.image.url) if request else img.image.url
        return getattr(img, "image_url", None) or None

    def get_room_primary_image_url(self, obj):
        room = getattr(obj, "room", None)
        if room is None:
            return None
        first = room.images.all().first() if hasattr(room, "images") else None
        if not first:
            return None
        return self._abs_image_url(first)

    def get_room_image_urls(self, obj):
        room = getattr(obj, "room", None)
        if room is None:
            return []
        if not hasattr(room, "images"):
            return []
        return [u for u in (self._abs_image_url(i) for i in room.images.all()) if u]

    class Meta:
        model = Booking
        fields = [
            "id",
            "client",
            "client_name",
            "client_phone",
            "client_passport",
            "client_dob",
            "room",
            "room_number",
            "room_base_price",
            "room_primary_image_url",
            "room_image_urls",
            "branch",
            "branch_name",
            "branch_number",
            "check_in_date",
            "check_out_date",
            "price_at_booking",
            "discount_amount",
            "final_price",
            "paid_total",
            "balance_due",
            "status",
            "source",
            "extensions",
            "has_active_extension",
            "can_cancel_extension",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "branch_number",
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
    client_phone = serializers.CharField(
        source="client.account.phone", read_only=True,
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
    room_primary_image_url = serializers.SerializerMethodField()
    paid_total = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()
    extensions = BookingExtensionSerializer(many=True, read_only=True)
    has_active_extension = serializers.SerializerMethodField()
    can_cancel_extension = serializers.SerializerMethodField()

    def get_paid_total(self, obj):
        return str(_balance_fields(obj)[0])

    def get_balance_due(self, obj):
        return str(_balance_fields(obj)[1])

    def get_has_active_extension(self, obj):
        return bool(_active_extensions(obj))

    def get_can_cancel_extension(self, obj):
        return bool(_active_extensions(obj)) and obj.status in (
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.PAID,
        )

    def get_room_primary_image_url(self, obj):
        room = getattr(obj, "room", None)
        if room is None:
            return None
        first = room.images.all().first() if hasattr(room, "images") else None
        if not first:
            return None
        request = self.context.get("request")
        if getattr(first, "image", None) and hasattr(first.image, "url"):
            return request.build_absolute_uri(first.image.url) if request else first.image.url
        return getattr(first, "image_url", None) or None

    class Meta:
        model = Booking
        fields = [
            "id",
            "client_name",
            "client_phone",
            "room",
            "room_number",
            "branch",
            "branch_name",
            "branch_number",
            "room_base_price",
            "room_primary_image_url",
            "check_in_date",
            "check_out_date",
            "price_at_booking",
            "discount_amount",
            "final_price",
            "paid_total",
            "balance_due",
            "status",
            "source",
            "extensions",
            "has_active_extension",
            "can_cancel_extension",
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
    date_of_birth = serializers.DateField()

    room = serializers.IntegerField(min_value=1)
    branch = serializers.IntegerField(min_value=1)
    # Check-in always inherits "today" — the admin website never pre-books
    # (that is a Telegram-only capability). Optional for backward compatibility.
    check_in_date = serializers.DateField(required=False)
    check_out_date = serializers.DateField()
    price_at_booking = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0,
    )
    # Payment is collected up-front during creation (no more "pending" gate).
    method = serializers.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES, required=False, default="cash",
    )

    # ── Strict per-field validation (ported from the Telegram Mini App) ──
    def validate_full_name(self, value):
        return validate_full_name(value, field="full_name")

    def validate_phone(self, value):
        return validate_uz_phone(value, field="phone")

    def validate_passport_number(self, value):
        return validate_passport(value, field="passport_number")

    def validate_date_of_birth(self, value):
        return validate_dob(value, field="date_of_birth", min_age=16)

    def validate(self, attrs):
        # Check-in inherits the current date when not supplied.
        if not attrs.get("check_in_date"):
            attrs["check_in_date"] = timezone.localdate()
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
    # Payment for the extra nights is collected immediately during extension.
    method = serializers.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES, required=False, default="cash",
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
