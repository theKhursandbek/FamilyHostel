from django.contrib import admin

from .models import AIResult, CleaningImage, CleaningTask


@admin.register(CleaningTask)
class CleaningTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "branch", "status", "priority", "assigned_to", "created_at")
    list_filter = ("status", "priority", "branch")


@admin.register(CleaningImage)
class CleaningImageAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "uploaded_at")


@admin.register(AIResult)
class AIResultAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "result", "ai_model_version", "created_at")
    list_filter = ("result",)
