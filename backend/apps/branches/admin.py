from django.contrib import admin

from .models import Branch, Room, RoomImage, RoomType


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "location", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "location")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "room_number", "branch", "room_type", "status", "is_active")
    list_filter = ("status", "is_active", "branch")
    search_fields = ("room_number",)


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "is_primary", "display_order", "uploaded_at")
