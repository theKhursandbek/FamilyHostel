"""Staff views (README Section 17)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import (
    IsDirectorOrHigher,
    IsOwnerOrDirectorOrHigher,
    IsStaffOrHigher,
    ReadOnly,
)

from .models import Attendance, ShiftAssignment
from .serializers import AttendanceSerializer, ShiftAssignmentSerializer


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """CRUD for shift assignments.

    Permission Matrix (README Section 18):
        - Assign shifts: Director ✅ | SuperAdmin ✅
        - Read: Staff and Admin can view their own shifts.
    """

    queryset = ShiftAssignment.objects.select_related(
        "account", "branch", "assigned_by",
    )
    serializer_class = ShiftAssignmentSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsDirectorOrHigher]
    filterset_fields = ["branch", "shift_type", "date", "role"]


class AttendanceViewSet(viewsets.ModelViewSet):
    """CRUD for attendance records.

    - Staff / Admin can create (check-in/out) and view their OWN records.
    - Director / SuperAdmin can view ALL attendance records.
    """

    queryset = Attendance.objects.select_related("account", "branch")
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsStaffOrHigher, IsOwnerOrDirectorOrHigher]
    owner_field = "account"  # used by IsOwnerOrDirectorOrHigher
    filterset_fields = ["branch", "shift_type", "date", "status"]
