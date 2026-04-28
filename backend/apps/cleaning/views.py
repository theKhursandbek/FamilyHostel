"""Cleaning views (README Section 17)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers, status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher, IsAssignedStaffOrDirectorOrHigher, IsDirectorOrHigher, IsStaffOrHigher
from apps.accounts.branch_scope import (
    enforce_branch_on_create,
    get_user_branch,
    scope_queryset_by_branch,
)

from .filters import CleaningTaskFilter
from .models import CleaningImage, CleaningTask
from .serializers import (
    CleaningImageSerializer,
    CleaningImageUploadSerializer,
    CleaningTaskListSerializer,
    CleaningTaskSerializer,
    OverrideSerializer,
)
from .services import assign_task_to_staff, complete_task, create_cleaning_task, director_assign_task, override_task, retry_task
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

    def get_queryset(self):
        """Restrict to the user's branch (SuperAdmin sees all).

        SuperAdmin may further narrow via ``?branch=<id>`` (handled by
        the django-filter ``CleaningTaskFilter``). For Director / Admin /
        Staff this is enforced at the queryset level so they can never
        see another branch's tasks even if they pass a different filter.
        """
        qs = super().get_queryset()
        return scope_queryset_by_branch(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return CleaningTaskListSerializer
        if self.action == "upload":
            return CleaningImageUploadSerializer
        if self.action == "override":
            return OverrideSerializer
        return CleaningTaskSerializer

    def perform_create(self, serializer):
        """Delegate creation to the service layer.

        Accepts an optional ``assigned_to`` (Staff PK) so an Admin / Director
        can pre-assign the task at creation time. Auto-created tasks (after
        a guest checkout, via the booking service) leave it ``None`` so any
        free staff member can self-pick it up.
        """
        data = serializer.validated_data
        # Enforce branch scoping: Director/Admin can only create within their
        # own branch; SuperAdmin must explicitly supply a branch (CEO picks it).
        branch = enforce_branch_on_create(self.request.user, data.get("branch"))
        room = data["room"]
        if room.branch_id != branch.pk:
            raise drf_serializers.ValidationError(
                {"room": "Selected room does not belong to the chosen branch."}
            )
        try:
            task = create_cleaning_task(
                room=room,
                branch=branch,
                priority=data.get("priority", "normal"),
                assigned_to=data.get("assigned_to"),
                performed_by=self.request.user,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages},
            )
        serializer.instance = task

    def perform_update(self, serializer):
        """Block edits only on completed tasks.

        Pending, in-progress and retry-required tasks remain editable so an
        admin / director can re-prioritise or reassign work even after a
        staff member has already picked it up. Once a task is ``completed``
        it represents a finished operational record and must not mutate.

        IMPORTANT: When the request changes ``assigned_to`` we route through
        :func:`director_assign_task` so the same one-task-per-staff rule and
        PENDING → IN_PROGRESS transition that exists at creation time is also
        applied to edits. Without this, a PATCH could silently park multiple
        tasks on the same staff member (and leave the status as PENDING,
        which in turn hides the Override button).
        """
        instance = self.get_object()
        if instance.status == CleaningTask.TaskStatus.COMPLETED:
            raise drf_serializers.ValidationError(
                {"detail": "Completed tasks cannot be edited."}
            )

        validated = serializer.validated_data
        new_assignee = validated.get("assigned_to", instance.assigned_to)
        assignment_changed = (
            "assigned_to" in validated
            and getattr(new_assignee, "pk", None) != getattr(instance.assigned_to, "pk", None)
        )

        # Apply the non-assignment edits first (priority, etc.) — but NEVER
        # let the raw save mutate ``assigned_to`` or ``status``; those go
        # through the service layer below.
        user_branch = get_user_branch(self.request.user)
        save_kwargs = {}
        if user_branch is not None:
            save_kwargs["branch"] = user_branch
        # Strip status/assigned_to from the raw save path.
        for forbidden in ("assigned_to", "status"):
            validated.pop(forbidden, None)
        serializer.save(**save_kwargs)

        # Now route the assignment change through the service for full validation.
        if assignment_changed:
            instance.refresh_from_db()
            try:
                if new_assignee is None:
                    # Director cleared the assignment — set back to PENDING.
                    instance.assigned_to = None
                    if instance.status == CleaningTask.TaskStatus.IN_PROGRESS:
                        instance.status = CleaningTask.TaskStatus.PENDING
                    instance.save(update_fields=["assigned_to", "status", "updated_at"])
                else:
                    director_assign_task(
                        task=instance,
                        staff_profile=new_assignee,
                        performed_by=self.request.user,
                    )
            except DjangoValidationError as exc:
                raise drf_serializers.ValidationError(
                    exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages},
                )
            instance.refresh_from_db()
            serializer.instance = instance

    def perform_destroy(self, instance):
        """Delete the task and write an audit entry.

        Only ``pending`` tasks may be deleted — once a staff member has
        started, retried, or completed work, the task represents a real
        operational event and must be preserved (use override/retry instead).

        Note: Deleting a still-pending task does NOT alter the room state
        (the room may have been moved into ``cleaning`` by booking checkout
        independently of this row's existence).
        """
        from apps.reports.services import log_action
        from .services import _task_snapshot
        if instance.status != CleaningTask.TaskStatus.PENDING:
            raise drf_serializers.ValidationError(
                {"detail": "Only pending tasks can be deleted. "
                           "Use override or retry for in-progress, retry, or completed tasks."}
            )
        snapshot = _task_snapshot(instance)
        pk = instance.pk
        super().perform_destroy(instance)
        log_action(
            account=self.request.user,
            action="cleaning_task.deleted",
            entity_type="CleaningTask",
            entity_id=pk,
            before_data=snapshot,
            after_data=None,
        )

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        """POST /cleaning-tasks/{pk}/assign/ — assign staff to task.

        Staff: self-assigns (no body needed).
        Director+: assigns any staff via ``{"staff_id": <int>}``.
        """
        task = self.get_object()
        user = request.user

        # Director / SuperAdmin can assign any staff via staff_id
        staff_id = request.data.get("staff_id")
        if staff_id is not None:
            if not (
                getattr(user, "is_director", False)
                or getattr(user, "is_superadmin", False)
            ):
                raise drf_serializers.ValidationError(
                    {"detail": "Only directors can assign staff to tasks."},
                )
            from apps.accounts.models import Staff

            try:
                target_staff = Staff.objects.get(pk=staff_id)
            except Staff.DoesNotExist:
                raise drf_serializers.ValidationError(
                    {"staff_id": "Staff not found."},
                )
            try:
                task = director_assign_task(
                    task=task,
                    staff_profile=target_staff,
                    performed_by=user,
                )
            except DjangoValidationError as exc:
                raise drf_serializers.ValidationError(exc.message_dict)
            serializer = CleaningTaskSerializer(
                task, context={"request": request},
            )
            return Response(serializer.data)

        # Staff self-assigns (existing behaviour)
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
        """POST /cleaning-tasks/{pk}/override/ — manual approval.

        Director and Super Admin can bypass the AI verdict and mark the
        task as completed (e.g. when a guest is waiting and AI is slow,
        or when AI keeps rejecting an obviously clean room). Administrators
        cannot override — they must escalate to the director. Requires
        ``reason`` in request body.
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
