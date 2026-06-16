"""
Mini App convenience endpoints for staff.

    GET /api/v1/staff/me/today/
        → {
            "shift": <ShiftAssignment | null>,
            "attendance": <Attendance | null>,
            "now": "<ISO timestamp>"
          }
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Attendance, ShiftAssignment
from .serializers import AttendanceSerializer, ShiftAssignmentSerializer


class MyTodayView(APIView):
    """Return the staff member's shift + attendance for the current day."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()

        shift = (
            ShiftAssignment.objects.filter(account=user, date=today)
            .select_related("branch")
            .first()
        )
        attendance = (
            Attendance.objects.filter(account=user, date=today)
            .select_related("branch")
            .first()
        )

        return Response({
            "now": timezone.now().isoformat(),
            "today": today.isoformat(),
            "shift": ShiftAssignmentSerializer(shift).data if shift else None,
            "attendance": AttendanceSerializer(attendance).data if attendance else None,
        })
