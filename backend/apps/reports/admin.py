from django.contrib import admin

from .models import AuditLog, FacilityLog, MonthlyReport, Notification, Penalty


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "month", "year", "created_by", "created_at")
    list_filter = ("branch", "year")


@admin.register(FacilityLog)
class FacilityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "type", "cost", "created_at")
    list_filter = ("type", "branch")


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "type", "count", "penalty_amount", "created_at")
    list_filter = ("type",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "type", "is_read", "created_at")
    list_filter = ("type", "is_read")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "role", "action", "entity_type", "entity_id", "created_at")
    list_filter = ("role", "action", "entity_type")
    readonly_fields = ("before_data", "after_data")
