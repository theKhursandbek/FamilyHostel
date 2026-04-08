"""
Reports views — Penalties, Facility Logs & Monthly Reports (Step 21.7).

Endpoints:
    Penalties:
        POST   /api/v1/penalties/             — create
        GET    /api/v1/penalties/             — list
        GET    /api/v1/penalties/{id}/        — retrieve
        PATCH  /api/v1/penalties/{id}/        — update
        DELETE /api/v1/penalties/{id}/        — delete

    Facility Logs:
        POST   /api/v1/facility-logs/         — create
        GET    /api/v1/facility-logs/         — list
        GET    /api/v1/facility-logs/{id}/    — retrieve
        PATCH  /api/v1/facility-logs/{id}/    — update

    Monthly Reports:
        GET    /api/v1/reports/monthly/           — list
        GET    /api/v1/reports/monthly/{id}/      — retrieve
        POST   /api/v1/reports/monthly/generate/  — generate
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.accounts.permissions import IsDirectorOrHigher, IsStaffOrHigher
from apps.branches.models import Branch

from .facility_service import create_facility_log, update_facility_log
from .filters import FacilityLogFilter, MonthlyReportFilter, PenaltyFilter
from .models import FacilityLog, MonthlyReport, Penalty
from .monthly_service import generate_monthly_report
from .penalty_service import create_penalty, delete_penalty, update_penalty
from .serializers import (
    CreateFacilityLogSerializer,
    CreatePenaltySerializer,
    FacilityLogSerializer,
    GenerateReportSerializer,
    MonthlyReportSerializer,
    PenaltySerializer,
    UpdateFacilityLogSerializer,
    UpdatePenaltySerializer,
)


# ==============================================================================
# PENALTY
# ==============================================================================


class PenaltyViewSet(viewsets.GenericViewSet):
    """
    Penalty management.

    Permission Matrix:
        - Director+: create, update, delete, list all in branch
        - Staff / Admin: view own penalties only
    """

    serializer_class = PenaltySerializer
    permission_classes = [IsAuthenticated, IsStaffOrHigher]
    filterset_class = PenaltyFilter
    ordering_fields = ["created_at", "penalty_amount", "type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Penalty.objects.select_related("account", "created_by")

        if user.is_superadmin:
            return qs
        if user.is_director:
            return qs.filter(created_by=user)
        # Staff / Admin — own penalties only
        return qs.filter(account=user)

    def list(self, request, *args, **kwargs):
        """GET /penalties/ — list with filtering."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /penalties/{id}/ — single penalty."""
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        """POST /penalties/ — create a penalty (Director+ only)."""
        if not (request.user.is_director or request.user.is_superadmin):
            raise drf_serializers.ValidationError(
                {"detail": "Only directors can create penalties."},
            )

        serializer = CreatePenaltySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Resolve account
        try:
            target_account = Account.objects.get(
                pk=serializer.validated_data["account"],
            )
        except Account.DoesNotExist:
            raise drf_serializers.ValidationError(
                {"account": "Account not found."},
            )

        try:
            penalty = create_penalty(
                account=target_account,
                penalty_type=serializer.validated_data["type"],
                count=serializer.validated_data.get("count", 1),
                penalty_amount=serializer.validated_data["penalty_amount"],
                reason=serializer.validated_data.get("reason", ""),
                created_by=request.user,
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(
            PenaltySerializer(penalty).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        """PATCH /penalties/{id}/ — update a penalty (Director+ only)."""
        if not (request.user.is_director or request.user.is_superadmin):
            raise drf_serializers.ValidationError(
                {"detail": "Only directors can update penalties."},
            )

        penalty = self.get_object()
        serializer = UpdatePenaltySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            penalty = update_penalty(
                penalty=penalty,
                performed_by=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(PenaltySerializer(penalty).data)

    def destroy(self, request, *args, **kwargs):
        """DELETE /penalties/{id}/ — delete a penalty (Director+ only)."""
        if not (request.user.is_director or request.user.is_superadmin):
            raise drf_serializers.ValidationError(
                {"detail": "Only directors can delete penalties."},
            )

        penalty = self.get_object()
        delete_penalty(penalty=penalty, performed_by=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==============================================================================
# FACILITY LOG
# ==============================================================================


class FacilityLogViewSet(viewsets.GenericViewSet):
    """
    Facility log management.

    Permission Matrix:
        - Director+: full CRUD
        - Admin: read-only
    """

    serializer_class = FacilityLogSerializer
    permission_classes = [IsAuthenticated, IsDirectorOrHigher]
    filterset_class = FacilityLogFilter
    ordering_fields = ["created_at", "type", "status", "cost"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = FacilityLog.objects.select_related("branch")

        if user.is_superadmin:
            return qs
        if user.is_director:
            director = user.director_profile  # type: ignore[union-attr]
            return qs.filter(branch=director.branch)
        return qs.none()

    def list(self, request, *args, **kwargs):
        """GET /facility-logs/ — list with filtering."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /facility-logs/{id}/ — single log."""
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        """POST /facility-logs/ — create a facility log."""
        serializer = CreateFacilityLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Resolve branch — from body or from director's branch
        branch_id = serializer.validated_data.get("branch")
        if branch_id:
            try:
                branch = Branch.objects.get(pk=branch_id)
            except Branch.DoesNotExist:
                raise drf_serializers.ValidationError(
                    {"branch": "Branch not found."},
                )
        else:
            director = getattr(request.user, "director_profile", None)
            if director is None:
                raise drf_serializers.ValidationError(
                    {"branch": "Branch is required."},
                )
            branch = director.branch

        try:
            log_entry = create_facility_log(
                branch=branch,
                facility_type=serializer.validated_data["type"],
                description=serializer.validated_data["description"],
                cost=serializer.validated_data.get("cost"),
                performed_by=request.user,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(
            FacilityLogSerializer(log_entry).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        """PATCH /facility-logs/{id}/ — update a facility log."""
        facility_log = self.get_object()
        serializer = UpdateFacilityLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            facility_log = update_facility_log(
                facility_log=facility_log,
                performed_by=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        return Response(FacilityLogSerializer(facility_log).data)


# ==============================================================================
# MONTHLY REPORT
# ==============================================================================


class MonthlyReportViewSet(viewsets.GenericViewSet):
    """
    Monthly report management.

    Permission Matrix:
        - Director+: generate and view
    """

    serializer_class = MonthlyReportSerializer
    permission_classes = [IsAuthenticated, IsDirectorOrHigher]
    filterset_class = MonthlyReportFilter
    ordering_fields = ["year", "month", "created_at"]
    ordering = ["-year", "-month"]

    def get_queryset(self):
        user = self.request.user
        qs = MonthlyReport.objects.select_related("branch", "created_by")

        if user.is_superadmin:
            return qs
        if user.is_director:
            director = user.director_profile  # type: ignore[union-attr]
            return qs.filter(branch=director.branch)
        return qs.none()

    def list(self, request, *args, **kwargs):
        """GET /reports/monthly/ — list reports."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """GET /reports/monthly/{id}/ — single report."""
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """POST /reports/monthly/generate/ — generate a monthly report."""
        serializer = GenerateReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        director_profile = getattr(request.user, "director_profile", None)
        if director_profile is None:
            raise drf_serializers.ValidationError(
                {"detail": "Director profile not found."},
            )

        try:
            report, summary = generate_monthly_report(
                branch=director_profile.branch,
                month=serializer.validated_data["month"],
                year=serializer.validated_data["year"],
                created_by=director_profile,
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict)

        data = MonthlyReportSerializer(report).data
        data["summary_data"] = summary
        return Response(data, status=status.HTTP_201_CREATED)
