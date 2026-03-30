from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "client", "room", "branch", "status",
        "check_in_date", "check_out_date", "final_price", "created_at",
    )
    list_filter = ("status", "branch", "created_at")
    search_fields = ("client__full_name", "room__room_number")
