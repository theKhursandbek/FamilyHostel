"""
Unit tests — Cleaning service layer.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.branches.models import Room
from apps.cleaning.models import CleaningTask
from apps.cleaning.services import assign_task_to_staff, complete_task, create_cleaning_task

from conftest import RoomFactory, StaffFactory


@pytest.mark.django_db
class TestCreateCleaningTask:
    """Tests for create_cleaning_task()."""

    def test_creates_pending_task(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        assert task.pk is not None
        assert task.status == "pending"
        assert task.room == room

    def test_cannot_create_duplicate_active_task(self, room, branch):
        create_cleaning_task(room=room, branch=branch)
        with pytest.raises(ValidationError, match="active cleaning task"):
            create_cleaning_task(room=room, branch=branch)


@pytest.mark.django_db
class TestAssignTask:
    """Tests for assign_task_to_staff()."""

    def test_assign_sets_staff_and_status(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        result = assign_task_to_staff(task=task, staff_profile=staff_profile)
        assert result.assigned_to == staff_profile
        assert result.status == "in_progress"

    def test_cannot_assign_non_pending_task(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        staff2 = StaffFactory()
        with pytest.raises(ValidationError, match="Cannot assign"):
            assign_task_to_staff(task=task, staff_profile=staff2)


@pytest.mark.django_db
class TestCompleteTask:
    """Tests for complete_task()."""

    def test_complete_sets_room_available(self, room, branch, staff_profile):
        task = create_cleaning_task(room=room, branch=branch)
        assign_task_to_staff(task=task, staff_profile=staff_profile)
        result = complete_task(task=task)
        assert result.status == "completed"
        assert result.completed_at is not None
        room.refresh_from_db()
        assert room.status == Room.RoomStatus.AVAILABLE

    def test_cannot_complete_pending_task(self, room, branch):
        task = create_cleaning_task(room=room, branch=branch)
        with pytest.raises(ValidationError, match="Only in-progress"):
            complete_task(task=task)
