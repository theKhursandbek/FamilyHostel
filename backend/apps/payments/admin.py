from django.contrib import admin

from .models import IncomeRule, Payment, SalaryRecord


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "amount", "payment_type", "is_paid", "paid_at", "created_at")
    list_filter = ("payment_type", "is_paid")


@admin.register(IncomeRule)
class IncomeRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "shift_type", "min_income", "max_income", "percent")
    list_filter = ("branch", "shift_type")


@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "amount", "period_start", "period_end", "status")
    list_filter = ("status",)
