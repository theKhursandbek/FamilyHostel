from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Account, Administrator, Client, Director, Staff, SuperAdmin


@admin.register(Account)
class AccountAdmin(BaseUserAdmin):
    list_display = ("id", "telegram_id", "phone", "is_active", "created_at")
    list_filter = ("is_active", "is_staff")
    search_fields = ("telegram_id", "phone")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("telegram_id", "phone", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("telegram_id", "phone", "password1", "password2"),
            },
        ),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "account", "created_at")
    search_fields = ("full_name",)


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "branch", "is_active", "hire_date")
    list_filter = ("is_active", "branch")
    search_fields = ("full_name",)


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "branch", "is_active")
    list_filter = ("is_active", "branch")
    search_fields = ("full_name",)


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "branch", "salary", "is_active")
    list_filter = ("is_active", "branch")
    search_fields = ("full_name",)


@admin.register(SuperAdmin)
class SuperAdminAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "account")
    search_fields = ("full_name",)
