"""
Integration tests — Cleaning API endpoints.
"""

import pytest
from django.urls import reverse

from apps.cleaning.models import CleaningTask
from apps.cleaning.services import create_cleaning_task

from conftest import RoomFactory


@pytest.mark.django_db
class TestCleaningAPI:
    """Test CleaningTaskViewSet via API."""

    def test_staff_can_list_tasks(self, staff_client, room, branch):
        create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-list")
        resp = staff_client.get(url)
        assert resp.status_code == 200

    def test_staff_can_assign_self(self, staff_client, staff_profile, room, branch):
        # Ensure staff is at same branch as the room
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        url = reverse("cleaning:cleaning-task-assign", args=[task.pk])
        resp = staff_client.post(url)
        assert resp.status_code == 200
        assert resp.data["status"] == "in_progress"

    def test_staff_can_complete_task(self, staff_client, staff_profile, room, branch):
        staff_profile.branch = branch
        staff_profile.save()
        task = create_cleaning_task(room=room, branch=branch)
        # Assign first
        assign_url = reverse("cleaning:cleaning-task-assign", args=[task.pk])
        staff_client.post(assign_url)
        # Complete
        complete_url = reverse("cleaning:cleaning-task-complete", args=[task.pk])
        resp = staff_client.post(complete_url)
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"
