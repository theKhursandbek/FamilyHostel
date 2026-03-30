"""Cleaning views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAssignedStaffOrDirectorOrHigher, IsStaffOrHigher

from .models import CleaningTask
from .serializers import CleaningTaskListSerializer, CleaningTaskSerializer


class CleaningTaskViewSet(viewsets.ModelViewSet):
    """CRUD for cleaning tasks.

    Permission Matrix (README Section 18):
        - Upload cleaning: Staff ✅ (assigned only)
        - Override AI: Director ✅ | SuperAdmin ✅
        - View tasks: Staff (own) | Admin (read) | Director | SuperAdmin

    Object-level: ``IsAssignedStaffOrDirectorOrHigher`` ensures Staff
    can only access their own tasks while Director+ can access all.
    """

    queryset = CleaningTask.objects.select_related(
        "room", "branch", "assigned_to",
    ).prefetch_related("images", "ai_results")
    permission_classes = [IsAuthenticated, IsStaffOrHigher, IsAssignedStaffOrDirectorOrHigher]
    filterset_fields = ["branch", "room", "status", "priority"]

    def get_serializer_class(self):
        if self.action == "list":
            return CleaningTaskListSerializer
        return CleaningTaskSerializer
