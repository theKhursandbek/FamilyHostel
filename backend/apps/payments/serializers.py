"""Payments serializers (README Section 14.4, 14.7)."""

from rest_framework import serializers

from .models import IncomeRule, Payment, SalaryRecord


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "booking",
            "amount",
            "payment_type",
            "is_paid",
            "paid_at",
            "created_by",
            "payment_intent_id",
            "stripe_event_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_paid",
            "paid_at",
            "payment_intent_id",
            "stripe_event_id",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        return value


class IncomeRuleSerializer(serializers.ModelSerializer):
    """
    Threshold-based income percentage rule.

    UX model: CEO sets `min_income` (the threshold above which the rule
    applies) and `percent`. The legacy `max_income` field is kept for
    backwards compatibility and defaults to a large sentinel — at
    calculation time the rule with the **highest** ``min_income`` ≤
    actual income wins.
    """

    SENTINEL_MAX = "999999999.99"

    max_income = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False,
    )

    class Meta:
        model = IncomeRule
        fields = [
            "id",
            "branch",
            "shift_type",
            "min_income",
            "max_income",
            "percent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        # Ensure max_income is always populated; default to sentinel if omitted
        # so the simplified threshold-only UI keeps the schema valid.
        if attrs.get("max_income") is None:
            attrs["max_income"] = self.SENTINEL_MAX
        if attrs.get("min_income") is not None and attrs["min_income"] < 0:
            raise serializers.ValidationError(
                {"min_income": "Threshold cannot be negative."},
            )
        if attrs.get("percent") is not None and (attrs["percent"] < 0 or attrs["percent"] > 100):
            raise serializers.ValidationError(
                {"percent": "Percent must be between 0 and 100."},
            )
        return attrs


class SalaryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryRecord
        fields = [
            "id",
            "account",
            "amount",
            "period_start",
            "period_end",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
