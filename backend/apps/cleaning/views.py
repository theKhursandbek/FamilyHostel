"""Cleaning views (README Section 17)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers, status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAssignedStaffOrDirectorOrHigher, IsDirectorOrHigher, IsStaffOrHigher

from .filters import CleaningTaskFilter
from .models import CleaningImage, CleaningTask
from .serializers import (
    CleaningImageSerializer,
    CleaningImageUploadSerializer,
    CleaningTaskListSerializer,
    CleaningTaskSerializer,
    OverrideSerializer,
)
from .services import assign_task_to_staff, complete_task, create_cleaning_task, override_task, retry_task
from .tasks import analyze_cleaning_images_task


class CleaningTaskViewSet(viewsets.ModelViewSet):
    """CRUD for cleaning tasks.

    Permission Matrix (README Section 18):
        - Upload cleaning: Staff ✅ (assigned only)
        - Override AI: Director ✅ | SuperAdmin ✅
        - View tasks: Staff (own) | Admin (read) | Director | SuperAdmin

    Object-level: ``IsAssignedStaffOrDirectorOrHigher`` ensures Staff
    can only access their own tasks while Director+ can access all.

    Custom actions:
        - POST /cleaning-tasks/{pk}/assign/    — Staff self-assigns
        - POST /cleaning-tasks/{pk}/complete/  — Complete after AI / override
        - POST /cleaning-tasks/{pk}/upload/    — Upload cleaning images
        - POST /cleaning-tasks/{pk}/retry/     — Re-open rejected task
        - POST /cleaning-tasks/{pk}/override/  — Director force-approve
    """

    queryset = CleaningTask.objects.select_related(
        "room", "room__branch", "branch", "assigned_to", "overridden_by",
    ).prefetch_related("images", "ai_results")
    permission_classes = [IsAuthenticated, IsStaffOrHigher, IsAssignedStaffOrDirectorOrHigher]
    filterset_class = CleaningTaskFilter
    ordering_fields = ["status", "priority", "created_at", "completed_at"]
    ordering = ["-created_at"]
    search_fields = ["room__room_number", "assigned_to__full_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return CleaningTaskListSerializer
        if self.action == "upload":
            return CleaningImageUploadSerializer
        if self.action == "override":
            return OverrideSerializer
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
        try:
            task = assign_task_to_staff(task=task, staff_profile=staff_profile)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        serializer = CleaningTaskSerializer(task, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/complete/ — mark task as completed."""
        task = self.get_object()
        try:
            task = complete_task(task=task, performed_by=request.user)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        serializer = CleaningTaskSerializer(task, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/upload/ — upload cleaning images.

        Only the assigned staff can upload images.
        After upload, triggers AI analysis via Celery.
        """
        task = self.get_object()

        # Only assigned staff can upload
        staff_profile = getattr(request.user, "staff_profile", None)
        if task.assigned_to is None or (
            staff_profile is None or staff_profile.pk != task.assigned_to_id
        ):
            # Directors+ can also upload
            if not (
                getattr(request.user, "is_director", False)
                or getattr(request.user, "is_superadmin", False)
            ):
                raise drf_serializers.ValidationError(
                    {"detail": "Only the assigned staff member can upload images."}
                )

        # Task must be in_progress or retry_required
        if task.status not in (
            CleaningTask.TaskStatus.IN_PROGRESS,
            CleaningTask.TaskStatus.RETRY_REQUIRED,
        ):
            raise drf_serializers.ValidationError(
                {"detail": f"Cannot upload images for task with status '{task.status}'."}
            )

        serializer = CleaningImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        images = serializer.validated_data["images"]
        created = []
        for image_file in images:
            img = CleaningImage.objects.create(task=task, image=image_file)
            created.append(img)

        # Trigger AI analysis
        analyze_cleaning_images_task.delay(task.pk)

        return Response(
            {
                "detail": f"{len(created)} image(s) uploaded. AI analysis queued.",
                "images": CleaningImageSerializer(
                    created, many=True, context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/retry/ — re-open rejected task.

        Only the assigned staff can retry.
        """
        task = self.get_object()
        try:
            task = retry_task(task=task, performed_by=request.user)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        serializer = CleaningTaskSerializer(task, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="override",
        permission_classes=[IsAuthenticated, IsDirectorOrHigher],
    )
    def override(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/override/ — Director force-approve.

        Requires ``reason`` in request body.
        """
        task = self.get_object()
        serializer = OverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            task = override_task(
                task=task,
                performed_by=request.user,
                reason=serializer.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(
            CleaningTaskSerializer(task, context={"request": request}).data,
        )
