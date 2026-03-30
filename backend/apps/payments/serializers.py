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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_paid", "paid_at", "created_at", "updated_at"]


class IncomeRuleSerializer(serializers.ModelSerializer):
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
