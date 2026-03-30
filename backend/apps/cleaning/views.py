"""Cleaning views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import CleaningTask
from .serializers import CleaningTaskListSerializer, CleaningTaskSerializer


class CleaningTaskViewSet(viewsets.ModelViewSet):
    """CRUD for cleaning tasks."""

    queryset = CleaningTask.objects.select_related(
        "room", "branch", "assigned_to",
    ).prefetch_related("images", "ai_results")
    permission_classes = [AllowAny]  # TODO: restrict to Staff/Admin/Director
    filterset_fields = ["branch", "room", "status", "priority"]

    def get_serializer_class(self):
        if self.action == "list":
            return CleaningTaskListSerializer
        return CleaningTaskSerializer
