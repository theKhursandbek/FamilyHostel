"""Staff views (README Section 17)."""

from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import (
    IsDirectorOrHigher,
    IsOwnerOrDirectorOrHigher,
    IsStaffOrHigher,
    ReadOnly,
)

from .models import Attendance, ShiftAssignment
from .serializers import AttendanceSerializer, ShiftAssignmentSerializer
from .services import check_in, check_out, create_shift_assignment, get_salary_summary


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

    def perform_create(self, serializer):
        """Delegate creation to the service layer (one-admin-per-shift check)."""
        data = serializer.validated_data
        assignment = create_shift_assignment(
            account=data["account"],
            role=data["role"],
            branch=data["branch"],
            shift_type=data["shift_type"],
            date=data["date"],
            assigned_by=data["assigned_by"],
        )
        serializer.instance = assignment


class AttendanceViewSet(viewsets.ModelViewSet):
    """CRUD for attendance records.

    - Staff / Admin can create (check-in/out) and view their OWN records.
    - Director / SuperAdmin can view ALL attendance records.

    Custom actions:
        - POST /attendance/{pk}/check-in/   — record check-in
        - POST /attendance/{pk}/check-out/   — record check-out
        - GET  /attendance/salary-summary/   — salary prep data
    """

    queryset = Attendance.objects.select_related("account", "branch")
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsStaffOrHigher, IsOwnerOrDirectorOrHigher]
    owner_field = "account"  # used by IsOwnerOrDirectorOrHigher
    filterset_fields = ["branch", "shift_type", "date", "status"]

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="check-in")
    def check_in_action(self, request):
        """POST /attendance/check-in/ — record check-in for today.

        Body: { "branch": <id>, "date": "YYYY-MM-DD", "shift_type": "day|night" }
        """
        branch_id = request.data.get("branch")
        date = request.data.get("date")
        shift_type = request.data.get("shift_type")

        if not all([branch_id, date, shift_type]):
            raise drf_serializers.ValidationError(
                {"detail": "branch, date, and shift_type are required."}
            )

        from apps.branches.models import Branch

        try:
            branch = Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist:
            raise drf_serializers.ValidationError({"branch": "Branch not found."})

        attendance = check_in(
            account=request.user,
            branch=branch,
            date=date,
            shift_type=shift_type,
        )
        serializer = AttendanceSerializer(attendance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out_action(self, request, pk=None):
        """POST /attendance/{pk}/check-out/ — record check-out."""
        attendance = self.get_object()
        attendance = check_out(attendance)
        serializer = AttendanceSerializer(attendance)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="salary-summary")
    def salary_summary(self, request):
        """GET /attendance/salary-summary/?account=&period_start=&period_end=

        Returns shift count, attendance stats, and completed cleaning tasks.
        Director+ can query any account; staff sees only own data.
        """
        from apps.accounts.models import Account

        account_id = request.query_params.get("account")
        period_start = request.query_params.get("period_start")
        period_end = request.query_params.get("period_end")

        if not all([period_start, period_end]):
            raise drf_serializers.ValidationError(
                {"detail": "period_start and period_end query params are required."}
            )

        # Director+ can query anyone; staff only themselves
        if account_id and (
            request.user.is_director or request.user.is_superadmin
        ):
            try:
                account = Account.objects.get(pk=account_id)
            except Account.DoesNotExist:
                raise drf_serializers.ValidationError(
                    {"account": "Account not found."}
                )
        else:
            account = request.user

        summary = get_salary_summary(
            account=account,
            period_start=period_start,
            period_end=period_end,
        )
        return Response(summary)
