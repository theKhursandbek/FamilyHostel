"""Staff views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import Attendance, ShiftAssignment
from .serializers import AttendanceSerializer, ShiftAssignmentSerializer


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """CRUD for shift assignments."""

    queryset = ShiftAssignment.objects.select_related(
        "account", "branch", "assigned_by",
    )
    serializer_class = ShiftAssignmentSerializer
    permission_classes = [AllowAny]  # TODO: restrict to Director
    filterset_fields = ["branch", "shift_type", "date", "role"]


class AttendanceViewSet(viewsets.ModelViewSet):
    """CRUD for attendance records."""

    queryset = Attendance.objects.select_related("account", "branch")
    serializer_class = AttendanceSerializer
    permission_classes = [AllowAny]  # TODO: restrict
    filterset_fields = ["branch", "shift_type", "date", "status"]
