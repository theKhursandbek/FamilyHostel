from django.contrib import admin

from .models import CashSession, SystemSettings


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "admin", "branch", "shift_type",
        "opening_balance", "closing_balance", "difference", "start_time",
    )
    list_filter = ("shift_type", "branch")


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "salary_mode", "salary_cycle", "shift_rate")
