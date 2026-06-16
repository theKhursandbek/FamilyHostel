"""
Tests for Step 21.1 — Cleaning System advanced features.

Covers:
    - Retry logic (AI rejected → retry_required → re-clean → resubmit)
    - Director override (force-approve + reason + audit log)
    - AI integration (Celery task stub + AIResult creation)
    - Image upload (real ImageField + multi-upload endpoint)
    - Task status flow (pending → in_progress → completed / retry_required)
    - Permission enforcement (assigned staff only, Director override anytime)
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from PIL import Image, ImageDraw
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.cleaning.ai.gemini import AIVerdict
from apps.cleaning.models import AIResult, CleaningImage, CleaningTask
from apps.cleaning.services import (
    analyze_cleaning_images,
    assign_task_to_staff,
    complete_task,
    create_cleaning_task,
    override_task,
    retry_task,
)
from apps.cleaning.tasks import analyze_cleaning_images_task
from conftest import DirectorFactory, RoomFactory, StaffFactory


# ==============================================================================
# HELPERS
# ==============================================================================


def _create_test_image(name: str = "test.jpg", seed: int = 0) -> io.BytesIO:
    """Create a small JPEG with seed-distinct content (distinct pHash)."""
    img = Image.new("RGB", (128, 128), color=(18, 18, 18))
    draw = ImageDraw.Draw(img)
    x = (seed * 17) % 80
    y = (seed * 29) % 80
    draw.rectangle([x, y, x + 40, y + 40], fill=(235, 235, 235))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    buf.name = name
    return buf


def _zone_payload(zones=None) -> dict:
    """Build a valid multipart payload: parallel images[] + zones[] lists."""
    zones = list(zones or CleaningImage.REQUIRED_ZONES)
    images = [_create_test_image(f"{z}.jpg", seed=i + 1) for i, z in enumerate(zones)]
    return {"images": images, "zones": zones}


def _approved_verdict(summary: str = "All zones clean and guest-ready.") -> AIVerdict:
    """A controllable APPROVED verdict for patching gemini.analyze."""
    return AIVerdict(
        result="approved",
        summary=summary,
        zones=[
            {"zone": z, "clean": True, "issues": []}
            for z in CleaningImage.REQUIRED_ZONES
        ],
        confidence=0.95,
        model_version="test-model",
    )


def _rejected_verdict(summary: str = "Trash left on the floor.") -> AIVerdict:
    """A controllable REJECTED verdict for patching gemini.analyze."""
    return AIVerdict(
        result="rejected",
        summary=summary,
        zones=[{"zone": "floor", "clean": False, "issues": ["trash on floor"]}],
        confidence=0.91,
        model_version="test-model",
    )


# ==============================================================================
# UNIT TESTS — Service layer: retry_task()
# ==============================================================================


@pytest.mark.django_db
class TestRetryTaskService:
    """Tests for retry_task()."""

    def test_retry_from_retry_required(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status"])

        result = retry_task(task=task, performed_by=staff_profile.account)
        assert result.status == CleaningTask.TaskStatus.IN_PROGRESS
        assert result.retry_count == 1

    def test_retry_increments_count(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)

        for i in range(3):
            task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
            task.save(update_fields=["status"])
            task = retry_task(task=task, performed_by=staff_profile.account)
            assert task.retry_count == i + 1

    def test_retry_only_from_retry_required(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        # in_progress — cannot retry
        with pytest.raises(ValidationError, match="retry_required"):
            retry_task(task=task, performed_by=staff_profile.account)

    def test_retry_pending_raises(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        with pytest.raises(ValidationError, match="retry_required"):
            retry_task(task=task)


# ==============================================================================
# UNIT TESTS — Service layer: override_task()
# ==============================================================================


@pytest.mark.django_db
class TestOverrideTaskService:
    """Tests for override_task()."""

    def test_override_pending_task(self, room, branch, director_profile):
        task = create_cleaning_task(room=room, branch=branch)
        result = override_task(
            task=task,
            performed_by=director_profile.account,
            reason="Room needed urgently",
        )
        assert result.status == CleaningTask.TaskStatus.COMPLETED
        assert result.override_reason == "Room needed urgently"
        assert result.overridden_by == director_profile.account
        assert result.completed_at is not None

    def test_override_in_progress_task(self, room, branch, staff_profile, director_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        result = override_task(
            task=task,
            performed_by=director_profile.account,
            reason="VIP guest",
        )
        assert result.status == CleaningTask.TaskStatus.COMPLETED

    def test_override_retry_required_task(self, room, branch, staff_profile, director_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status"])

        result = override_task(
            task=task,
            performed_by=director_profile.account,
            reason="No time for re-clean",
        )
        assert result.status == CleaningTask.TaskStatus.COMPLETED

    def test_override_completed_raises(self, room, branch, staff_profile, director_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        complete_task(task=task)
        with pytest.raises(ValidationError, match="already completed"):
            override_task(task=task, performed_by=director_profile.account, reason="x")

    def test_override_sets_room_available(self, room, branch, director_profile):
        from apps.branches.models import Room

        room.status = Room.RoomStatus.CLEANING
        room.save()
        task = create_cleaning_task(room=room, branch=branch)
        override_task(
            task=task,
            performed_by=director_profile.account,
            reason="Override test",
        )
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.AVAILABLE


# ==============================================================================
# UNIT TESTS — Service layer: analyze_cleaning_images()
# ==============================================================================


@pytest.mark.django_db
class TestAnalyzeCleaningImagesService:
    """Tests for the analyze_cleaning_images() shim (delegates to Gemini)."""

    def test_no_images_returns_rejected(self, room, branch):
        # No photos at all -> the analyser fails closed (rejected).
        task = create_cleaning_task(room=room, branch=branch)
        result, feedback = analyze_cleaning_images(task)
        assert result == AIResult.Result.REJECTED
        assert feedback  # a human-readable reason is always provided

    def test_with_images_returns_approved(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded = SimpleUploadedFile(
            "bed.jpg", _create_test_image(seed=1).read(), content_type="image/jpeg",
        )
        CleaningImage.objects.create(task=task, image=uploaded, zone="bed")

        with patch(
            "apps.cleaning.ai.gemini.analyze", return_value=_approved_verdict(),
        ):
            result, feedback = analyze_cleaning_images(task)

        assert result == AIResult.Result.APPROVED
        assert feedback == "All zones clean and guest-ready."


# ==============================================================================
# UNIT TESTS — Celery task: analyze_cleaning_images_task
# ==============================================================================


@pytest.mark.django_db
class TestAnalyzeCleaningImagesTask:
    """Tests for the Celery task that triggers AI analysis."""

    def test_task_creates_ai_result(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        # No images → rejected
        result = analyze_cleaning_images_task(task.pk)
        assert result["result"] == "rejected"
        assert AIResult.objects.filter(task=task).count() == 1

        # Task should be retry_required
        task.refresh_from_db()
        assert task.status == CleaningTask.TaskStatus.RETRY_REQUIRED

    def test_task_approved_with_images(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)

        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded = SimpleUploadedFile(
            "bed.jpg", _create_test_image(seed=2).read(), content_type="image/jpeg",
        )
        CleaningImage.objects.create(task=task, image=uploaded, zone="bed")

        with patch(
            "apps.cleaning.ai.gemini.analyze", return_value=_approved_verdict(),
        ):
            result = analyze_cleaning_images_task(task.pk)
        assert result["result"] == "approved"

        # AI approval auto-completes the task (anti-cheat: no manual staff step).
        task.refresh_from_db()
        assert task.status == CleaningTask.TaskStatus.COMPLETED

    def test_task_not_found(self):
        result = analyze_cleaning_images_task(99999)
        assert result["result"] == "error"
        assert "not found" in result["feedback"]


# ==============================================================================
# INTEGRATION TESTS — Image upload endpoint
# ==============================================================================


@pytest.mark.django_db
class TestImageUploadEndpoint:
    """POST /cleaning/tasks/{pk}/upload/"""

    def test_staff_can_upload_images(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)

        url = reverse("cleaning:cleaning-task-upload", args=[task.pk])
        with patch("apps.cleaning.views.analyze_cleaning_images_task") as mock_ai:
            mock_ai.delay = lambda pk: None
            response: Response = staff_client.post(  # type: ignore[assignment]
                url, _zone_payload(), format="multipart",
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert CleaningImage.objects.filter(task=task).count() == 4

    def test_upload_multiple_images(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)

        url = reverse("cleaning:cleaning-task-upload", args=[task.pk])
        payload = _zone_payload(["bed", "bathroom", "floor", "trash", "extra"])
        with patch("apps.cleaning.views.analyze_cleaning_images_task") as mock_ai:
            mock_ai.delay = lambda pk: None
            response: Response = staff_client.post(  # type: ignore[assignment]
                url, payload, format="multipart",
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert CleaningImage.objects.filter(task=task).count() == 5

    def test_upload_rejected_for_pending_task(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        # Task is pending, not assigned — cannot upload
        url = reverse("cleaning:cleaning-task-upload", args=[task.pk])
        response: Response = staff_client.post(  # type: ignore[assignment]
            url, _zone_payload(), format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unassigned_staff_cannot_upload(self, api_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        # Assign to a different staff
        other_staff = StaffFactory(branch=branch)
        assign_task_to_staff(task=task, staff_profile=other_staff)

        api_client.force_authenticate(user=staff_profile.account)
        url = reverse("cleaning:cleaning-task-upload", args=[task.pk])
        response: Response = api_client.post(  # type: ignore[assignment]
            url, _zone_payload(), format="multipart",
        )
        # Object-level permission denies access (not assigned to this task)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# INTEGRATION TESTS — Retry endpoint
# ==============================================================================


@pytest.mark.django_db
class TestRetryEndpoint:
    """POST /cleaning/tasks/{pk}/retry/"""

    def test_staff_can_retry_rejected_task(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status"])

        url = reverse("cleaning:cleaning-task-retry", args=[task.pk])
        response: Response = staff_client.post(url)  # type: ignore[assignment]
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "in_progress"  # type: ignore[index]
        assert response.data["retry_count"] == 1  # type: ignore[index]

    def test_cannot_retry_non_retry_required(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)

        url = reverse("cleaning:cleaning-task-retry", args=[task.pk])
        response: Response = staff_client.post(url)  # type: ignore[assignment]
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# INTEGRATION TESTS — Director override endpoint
# ==============================================================================


@pytest.mark.django_db
class TestOverrideEndpoint:
    """POST /cleaning/tasks/{pk}/override/"""

    def test_director_can_override(self, director_client, director_profile, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = director_client.post(  # type: ignore[assignment]
            url, {"reason": "VIP guest arriving soon"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"  # type: ignore[index]
        assert response.data["override_reason"] == "VIP guest arriving soon"  # type: ignore[index]
        assert response.data["overridden_by"] == director_profile.account.pk  # type: ignore[index]

    def test_override_without_reason_succeeds(self, director_client, room, branch):
        # "Mark Cleaned" reason is OPTIONAL — posting none still completes.
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = director_client.post(url, {})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"  # type: ignore[index]
        assert response.data["override_reason"] == ""  # type: ignore[index]

    def test_override_short_reason_accepted(self, director_client, room, branch):
        # No minimum length anymore — any (or no) note is accepted.
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = director_client.post(url, {"reason": "ab"})  # type: ignore[assignment]
        assert response.status_code == status.HTTP_200_OK
        assert response.data["override_reason"] == "ab"  # type: ignore[index]

    def test_staff_cannot_override(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = staff_client.post(  # type: ignore[assignment]
            url, {"reason": "Trying to override"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_override(self, admin_client, room, branch):
        # "Mark Cleaned" is now an Admin+ supervisor power.
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = admin_client.post(  # type: ignore[assignment]
            url, {"reason": "Admin marking cleaned"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"  # type: ignore[index]

    def test_override_already_completed_fails(
        self, director_client, staff_profile, room, branch,
    ):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        complete_task(task=task)

        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = director_client.post(  # type: ignore[assignment]
            url, {"reason": "Already done"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# INTEGRATION TESTS — Full status flow
# ==============================================================================


@pytest.mark.django_db
class TestTaskStatusFlow:
    """Test the complete lifecycle of a cleaning task."""

    def test_happy_path(self, staff_client, staff_profile, director_profile, room, branch):
        """pending → in_progress (staff) → completed (supervisor)."""
        staff_profile.branch = branch
        staff_profile.save()

        task = create_cleaning_task(room=room, branch=branch)
        assert task.status == "pending"

        # Staff self-assigns
        assign_url = reverse("cleaning:cleaning-task-assign", args=[task.pk])
        resp = staff_client.post(assign_url)
        assert resp.data["status"] == "in_progress"

        # Staff can no longer self-complete (anti-cheat) — a supervisor does.
        complete_url = reverse("cleaning:cleaning-task-complete", args=[task.pk])
        denied = staff_client.post(complete_url)
        assert denied.status_code == status.HTTP_403_FORBIDDEN

        # Re-auth the shared client as a director and complete.
        staff_client.force_authenticate(user=director_profile.account)
        resp = staff_client.post(complete_url)
        assert resp.data["status"] == "completed"

    def test_retry_path(self, staff_client, staff_profile, director_profile, room, branch):
        """pending → in_progress → retry_required → in_progress → completed"""
        staff_profile.branch = branch
        staff_profile.save()

        task = create_cleaning_task(room=room, branch=branch)

        # Assign
        assign_url = reverse("cleaning:cleaning-task-assign", args=[task.pk])
        staff_client.post(assign_url)

        # Simulate AI rejection
        task.refresh_from_db()
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status"])

        # Retry
        retry_url = reverse("cleaning:cleaning-task-retry", args=[task.pk])
        resp = staff_client.post(retry_url)
        assert resp.data["status"] == "in_progress"
        assert resp.data["retry_count"] == 1

        # Complete after retry — supervisor (re-auth shared client as director).
        staff_client.force_authenticate(user=director_profile.account)
        complete_url = reverse("cleaning:cleaning-task-complete", args=[task.pk])
        resp = staff_client.post(complete_url)
        assert resp.data["status"] == "completed"

    def test_override_path(self, director_client, room, branch):
        """pending → override → completed"""
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        resp: Response = director_client.post(  # type: ignore[assignment]
            url, {"reason": "Emergency override"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "completed"  # type: ignore[index]

    def test_assign_retry_required_task(self, room, branch, staff_profile):
        """Staff can re-assign a retry_required task."""
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.assigned_to = None
        task.save(update_fields=["status", "assigned_to"])

        new_staff = StaffFactory(branch=branch)
        result = assign_task_to_staff(task=task, staff_profile=new_staff)
        assert result.assigned_to == new_staff
        assert result.status == CleaningTask.TaskStatus.IN_PROGRESS

    def test_complete_retry_required_task(self, room, branch, staff_profile):
        """retry_required tasks can also be completed directly."""
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        task.status = CleaningTask.TaskStatus.RETRY_REQUIRED
        task.save(update_fields=["status"])

        result = complete_task(task=task, performed_by=staff_profile.account)
        assert result.status == CleaningTask.TaskStatus.COMPLETED


# ==============================================================================
# INTEGRATION TESTS — Permission enforcement for cleaning
# ==============================================================================


@pytest.mark.django_db
class TestCleaningPermissions:
    """Ensure only assigned staff or Director+ can act on tasks."""

    def test_unauthenticated_cannot_list(self):
        client = APIClient()
        url = reverse("cleaning:cleaning-task-list")
        response: Response = client.get(url)  # type: ignore[assignment]
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_client_cannot_list(self, api_client, client_profile):
        api_client.force_authenticate(user=client_profile.account)
        url = reverse("cleaning:cleaning-task-list")
        response: Response = api_client.get(url)  # type: ignore[assignment]
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_director_can_access_any_task(
        self, director_client, staff_profile, room, branch,
    ):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        url = reverse("cleaning:cleaning-task-detail", args=[task.pk])
        response = director_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_superadmin_can_override(
        self, superadmin_client, room, branch,
    ):
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-override", args=[task.pk])
        response: Response = superadmin_client.post(  # type: ignore[assignment]
            url, {"reason": "SuperAdmin override test"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"  # type: ignore[index]


# ==============================================================================
# MODEL TESTS
# ==============================================================================


@pytest.mark.django_db
class TestCleaningModels:
    """Test model-level constraints and defaults."""

    def test_cleaning_task_defaults(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        assert task.retry_count == 0
        assert task.override_reason == ""
        assert task.overridden_by is None

    def test_cleaning_image_with_real_file(self, room, branch):
        from django.core.files.uploadedfile import SimpleUploadedFile

        task = create_cleaning_task(room=room, branch=branch)
        img = _create_test_image()
        uploaded = SimpleUploadedFile("room.jpg", img.read(), content_type="image/jpeg")
        ci = CleaningImage.objects.create(task=task, image=uploaded)
        assert ci.pk is not None
        assert ci.image.name.startswith("cleaning_images/")

    def test_ai_result_choices(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        approved = AIResult.objects.create(
            task=task, result=AIResult.Result.APPROVED, feedback_text="Good",
        )
        rejected = AIResult.objects.create(
            task=task, result=AIResult.Result.REJECTED, feedback_text="Bad",
        )
        assert approved.result == "approved"
        assert rejected.result == "rejected"

    def test_task_str_representation(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        assert "pending" in str(task)
