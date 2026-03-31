"""Cleaning views (README Section 17)."""

from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAssignedStaffOrDirectorOrHigher, IsStaffOrHigher

from .filters import CleaningTaskFilter
from .models import CleaningTask
from .serializers import CleaningTaskListSerializer, CleaningTaskSerializer
from .services import assign_task_to_staff, complete_task, create_cleaning_task


class CleaningTaskViewSet(viewsets.ModelViewSet):
    """CRUD for cleaning tasks.

    Permission Matrix (README Section 18):
        - Upload cleaning: Staff ✅ (assigned only)
        - Override AI: Director ✅ | SuperAdmin ✅
        - View tasks: Staff (own) | Admin (read) | Director | SuperAdmin

    Object-level: ``IsAssignedStaffOrDirectorOrHigher`` ensures Staff
    can only access their own tasks while Director+ can access all.

    Custom actions:
        - POST /cleaning-tasks/{pk}/assign/   — Staff self-assigns
        - POST /cleaning-tasks/{pk}/complete/  — Complete after AI / override
    """

    queryset = CleaningTask.objects.select_related(
        "room", "room__branch", "branch", "assigned_to",
    ).prefetch_related("images", "ai_results")
    permission_classes = [IsAuthenticated, IsStaffOrHigher, IsAssignedStaffOrDirectorOrHigher]
    filterset_class = CleaningTaskFilter
    ordering_fields = ["status", "priority", "created_at", "completed_at"]
    ordering = ["-created_at"]
    search_fields = ["room__room_number", "assigned_to__full_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return CleaningTaskListSerializer
        return CleaningTaskSerializer

    def perform_create(self, serializer):
        """Delegate creation to the service layer."""
        data = serializer.validated_data
        task = create_cleaning_task(
            room=data["room"],
            branch=data["branch"],
            priority=data.get("priority", "normal"),
            performed_by=self.request.user,
        )
        serializer.instance = task

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/assign/ — staff self-assigns."""
        task = self.get_object()
        # The request user must have a staff_profile
        staff_profile = getattr(request.user, "staff_profile", None)
        if staff_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Only staff members can self-assign tasks."}
            )
        task = assign_task_to_staff(task=task, staff_profile=staff_profile)
        serializer = CleaningTaskSerializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/complete/ — mark task as completed."""
        task = self.get_object()
        task = complete_task(task=task, performed_by=request.user)
        serializer = CleaningTaskSerializer(task)
        return Response(serializer.data)
