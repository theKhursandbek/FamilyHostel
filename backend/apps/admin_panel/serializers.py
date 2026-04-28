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
    """Read-only representation of a cash session.

    Adds friendly aliases (`opened_at`/`closed_at`/`administrator`) and
    derived fields (`admin_name`, `branch_name`, `expected_balance`,
    `variance`) so the frontend doesn't need to chase joins or guess
    field names.
    """

    # --- Friendly aliases ---
    opened_at = serializers.DateTimeField(source="start_time", read_only=True)
    closed_at = serializers.DateTimeField(source="end_time", read_only=True)
    administrator = serializers.IntegerField(source="admin_id", read_only=True)

    # --- Derived display fields ---
    admin_name = serializers.SerializerMethodField()
    administrator_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    handed_over_to_name = serializers.SerializerMethodField()
    expected_balance = serializers.SerializerMethodField()
    cash_in = serializers.SerializerMethodField()
    cash_out = serializers.SerializerMethodField()
    variance = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    variance_note_threshold = serializers.SerializerMethodField()

    class Meta:
        model = CashSession
        fields = [
            "id",
            "admin",
            "admin_name",
            "administrator",
            "administrator_name",
            "branch",
            "branch_name",
            "shift_type",
            "start_time",
            "end_time",
            "opened_at",
            "closed_at",
            "opening_balance",
            "closing_balance",
            "expected_balance",
            "cash_in",
            "cash_out",
            "difference",
            "variance",
            "is_open",
            "note",
            "handed_over_to",
            "handed_over_to_name",
            "variance_status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_comment",
            "variance_note_threshold",
            "updated_at",
        ]
        read_only_fields = fields

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _admin_label(admin):
        if admin is None:
            return None
        full = getattr(admin, "full_name", None)
        if full:
            return full
        account = getattr(admin, "account", None)
        return getattr(account, "phone", None) or f"Admin #{admin.pk}"

    def get_admin_name(self, obj):
        return self._admin_label(obj.admin)

    def get_administrator_name(self, obj):
        return self._admin_label(obj.admin)

    def get_branch_name(self, obj):
        return getattr(obj.branch, "name", None) or (
            f"Branch #{obj.branch_id}" if obj.branch_id else None
        )

    def get_handed_over_to_name(self, obj):
        return self._admin_label(obj.handed_over_to)

    def get_is_open(self, obj):
        return obj.end_time is None

    def _flows(self, obj):
        """Return ``(cash_in, cash_out)`` for the session window.

        cash_in  — cash payments collected for bookings in this branch
                   between session open and (close or now).
        cash_out — facility-log expenses (Products, Detergents, Repair, …)
                   recorded for this branch in the same window. If the log
                   carries a `shift_type`, it must match this session's
                   shift; logs without one fall through to whichever
                   session is open at that moment.
        """
        from django.db.models import Q, Sum
        from django.utils import timezone

        from apps.payments.models import Payment
        from apps.reports.models import FacilityLog

        end = obj.end_time or timezone.now()

        cash_in = (
            Payment.objects.filter(
                booking__branch_id=obj.branch_id,
                method=Payment.PaymentMethod.CASH,
                is_paid=True,
                paid_at__gte=obj.start_time,
                paid_at__lte=end,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        cash_out = (
            FacilityLog.objects.filter(
                branch_id=obj.branch_id,
                status=FacilityLog.LogStatus.PAID,
                payment_method=FacilityLog.PaymentMethod.CASH,
                paid_at__gte=obj.start_time,
                paid_at__lte=end,
            )
            .filter(
                Q(shift_type=obj.shift_type)
                | Q(shift_type__isnull=True)
                | Q(shift_type="")
            )
            .aggregate(total=Sum("cost"))["total"]
            or 0
        )

        return cash_in, cash_out

    def get_cash_in(self, obj):
        cash_in, _ = self._flows(obj)
        return str(cash_in)

    def get_cash_out(self, obj):
        _, cash_out = self._flows(obj)
        return str(cash_out)

    def get_expected_balance(self, obj):
        from decimal import Decimal

        cash_in, cash_out = self._flows(obj)
        return str(
            Decimal(obj.opening_balance or 0) + Decimal(cash_in) - Decimal(cash_out)
        )

    def get_variance(self, obj):
        """Counted cash minus expected. Positive = surplus, negative = shortage."""
        if obj.closing_balance is None:
            return None
        from decimal import Decimal

        cash_in, cash_out = self._flows(obj)
        expected = (
            Decimal(obj.opening_balance or 0) + Decimal(cash_in) - Decimal(cash_out)
        )
        return str(Decimal(obj.closing_balance) - expected)


    def get_reviewed_by_name(self, obj):
        director = obj.reviewed_by
        if director is None:
            return None
        full = getattr(director, "full_name", None)
        if full:
            return full
        account = getattr(director, "account", None)
        return getattr(account, "phone", None) or f"Director #{director.pk}"

    def get_variance_note_threshold(self, _obj):
        """Expose the policy threshold so the UI can require notes live."""
        from .services import VARIANCE_NOTE_THRESHOLD

        return str(VARIANCE_NOTE_THRESHOLD)


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


class ReviewCashSessionSerializer(serializers.Serializer):
    """Validates input for a director's review of a closed cash session."""

    decision = serializers.ChoiceField(
        choices=[
            (CashSession.VarianceStatus.APPROVED, "Approve"),
            (CashSession.VarianceStatus.DISPUTED, "Dispute"),
        ],
    )
    comment = serializers.CharField(required=False, default="", allow_blank=True)
