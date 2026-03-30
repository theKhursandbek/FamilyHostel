from django.contrib import admin

from .models import Attendance, ShiftAssignment


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "role", "branch", "shift_type", "date", "assigned_by")
    list_filter = ("role", "shift_type", "branch", "date")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "branch", "date", "shift_type", "status", "check_in", "check_out")
    list_filter = ("status", "shift_type", "branch", "date")
