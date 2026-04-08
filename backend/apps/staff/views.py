"""Staff views (README Section 17 & Step 21.5)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import (
    IsDirectorOrHigher,
    IsOwnerOrDirectorOrHigher,
    IsStaffOrHigher,
    ReadOnly,
)

from .day_off_service import (
    approve_day_off_request,
    create_day_off_request,
    reject_day_off_request,
)
from .filters import AttendanceFilter, DayOffRequestFilter, ShiftAssignmentFilter
from .models import Attendance, DayOffRequest, ShiftAssignment
from .serializers import (
    AttendanceSerializer,
    CreateDayOffRequestSerializer,
    DayOffRequestSerializer,
    ReviewDayOffRequestSerializer,
    ShiftAssignmentSerializer,
)
from .services import check_in, check_out, create_shift_assignment, get_salary_summary


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """CRUD for shift assignments.

    Permission Matrix (README Section 18):
        - Assign shifts: Director ✅ | SuperAdmin ✅
        - Read: Staff and Admin can view their own shifts.
    """

    queryset = ShiftAssignment.objects.select_related(
        "account", "branch", "assigned_by", "assigned_by__account",
    )
    serializer_class = ShiftAssignmentSerializer
    permission_classes = [IsAuthenticated, ReadOnly | IsDirectorOrHigher]
    filterset_class = ShiftAssignmentFilter
    ordering_fields = ["date", "shift_type", "role", "created_at"]
    ordering = ["-date"]
    search_fields = ["account__phone"]

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
    filterset_class = AttendanceFilter
    ordering_fields = ["date", "shift_type", "status", "check_in", "check_out"]
    ordering = ["-date"]
    search_fields = ["account__phone"]

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


# ==============================================================================
# DAY-OFF REQUEST VIEWSET (Step 21.5)
# ==============================================================================


class DayOffRequestViewSet(viewsets.GenericViewSet):
    """
    Day-off requests for staff / administrators.

    Endpoints:
        POST   /day-off-requests/              — create request (staff+)
        GET    /day-off-requests/              — list requests
        GET    /day-off-requests/{id}/         — retrieve one request
        POST   /day-off-requests/{id}/approve/ — director approves
        POST   /day-off-requests/{id}/reject/  — director rejects

    Permission Matrix:
        - Staff / Admin: CRUD on **own** requests only
        - Director / SuperAdmin: view branch requests + approve/reject
    """

    serializer_class = DayOffRequestSerializer
    permission_classes = [IsAuthenticated, IsStaffOrHigher]
    filterset_class = DayOffRequestFilter
    ordering_fields = ["start_date", "end_date", "status", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Staff / Admin see only their own requests.
        Director sees branch-level requests.
        SuperAdmin sees all.
        """
        user = self.request.user
        qs = DayOffRequest.objects.select_related(
            "account", "branch", "reviewed_by", "reviewed_by__account",
        )

        if user.is_superadmin:
            return qs
        if user.is_director:
            director = user.director_profile  # type: ignore[union-attr]
            return qs.filter(branch=director.branch)
        # Staff / Admin — own requests only
        return qs.filter(account=user)

    def list(self, request, *args, **kwargs):
        """GET /day-off-requests/ — list with filtering & ordering."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /day-off-requests/{id}/ — retrieve a single request."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """POST /day-off-requests/ — submit a new day-off request."""
        serializer = CreateDayOffRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Determine the branch for the requesting user
        branch = self._resolve_branch(request.user)
        if branch is None:
            raise drf_serializers.ValidationError(
                {"branch": "Cannot determine your branch. Contact your director."},
            )

        try:
            day_off = create_day_off_request(
                account=request.user,
                branch=branch,
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        return Response(
            DayOffRequestSerializer(day_off).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="approve",
        permission_classes=[IsAuthenticated, IsDirectorOrHigher],
    )
    def approve(self, request, pk=None):
        """POST /day-off-requests/{id}/approve/ — approve a pending request."""
        day_off = self.get_object()
        review_ser = ReviewDayOffRequestSerializer(data=request.data)
        review_ser.is_valid(raise_exception=True)

        director_profile = self._resolve_director(request.user)
        if director_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Director profile not found."},
            )

        try:
            day_off = approve_day_off_request(
                day_off_request=day_off,
                reviewed_by=director_profile,
                comment=review_ser.validated_data.get("comment", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        return Response(DayOffRequestSerializer(day_off).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
        permission_classes=[IsAuthenticated, IsDirectorOrHigher],
    )
    def reject(self, request, pk=None):
        """POST /day-off-requests/{id}/reject/ — reject a pending request."""
        day_off = self.get_object()
        review_ser = ReviewDayOffRequestSerializer(data=request.data)
        review_ser.is_valid(raise_exception=True)

        director_profile = self._resolve_director(request.user)
        if director_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Director profile not found."},
            )

        try:
            day_off = reject_day_off_request(
                day_off_request=day_off,
                reviewed_by=director_profile,
                comment=review_ser.validated_data.get("comment", ""),
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)
        return Response(DayOffRequestSerializer(day_off).data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_branch(user):
        """Determine the branch for a staff/admin/director user."""
        for attr in ("staff_profile", "administrator_profile", "director_profile"):
            profile = getattr(user, attr, None)
            if profile is not None:
                return getattr(profile, "branch", None)
        return None

    @staticmethod
    def _resolve_director(user):
        """Return the Director profile for the user (or None)."""
        director = getattr(user, "director_profile", None)
        if director:
            return director
        # SuperAdmin: create a synthetic ref if needed — fall back to first
        # director record (SuperAdmin has no Director profile by default).
        superadmin = getattr(user, "superadmin_profile", None)
        if superadmin:
            # Try to find a Director profile on the same account (multi-role)
            director = getattr(user, "director_profile", None)
            if director:
                return director
            # Use the first active director as the reviewer
            from apps.accounts.models import Director
            return Director.objects.filter(is_active=True).first()
        return None
