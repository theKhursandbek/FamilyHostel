"""
Dashboard API views (Step 21.3).

Endpoints:
    GET /api/v1/dashboard/admin/       → AdminDashboardView
    GET /api/v1/dashboard/director/    → DirectorDashboardView
    GET /api/v1/dashboard/super-admin/ → SuperAdminDashboardView

All responses are wrapped by ``StandardJSONRenderer`` into
``{success: true, data: {...}}``.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    IsAdministrator,
    IsAdminOrHigher,
    IsDirectorOrHigher,
    IsSuperAdmin,
)
from apps.admin_panel.dashboard_service import (
    get_admin_dashboard,
    get_director_dashboard,
    get_super_admin_dashboard,
)


class AdminDashboardView(APIView):
    """
    GET /api/v1/dashboard/admin/

    Returns dashboard data for the requesting Administrator.
    Permission: Administrator (or Director / SuperAdmin).
    """

    permission_classes = [IsAuthenticated, IsAdminOrHigher]

    def get(self, request: Request) -> Response:
        user = request.user

        # Administrators see their own dashboard.
        # Directors / SuperAdmins also allowed (may inspect any admin dashboard
        # via ?account_id= query param in future; for now own branch only).
        if not hasattr(user, "administrator_profile"):
            return Response(
                {"detail": "You do not have an Administrator profile."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = get_admin_dashboard(user)
        return Response(data)


class DirectorDashboardView(APIView):
    """
    GET /api/v1/dashboard/director/

    Returns dashboard data for the requesting Director's branch.
    Permission: Director or SuperAdmin.
    """

    permission_classes = [IsAuthenticated, IsDirectorOrHigher]

    def get(self, request: Request) -> Response:
        user = request.user

        if hasattr(user, "director_profile"):
            branch = user.director_profile.branch
        elif hasattr(user, "superadmin_profile"):
            # SuperAdmin must specify branch_id
            branch_id = request.query_params.get("branch_id")
            if not branch_id:
                return Response(
                    {"detail": "branch_id query parameter is required for Super Admin."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from apps.branches.models import Branch

            try:
                branch = Branch.objects.get(pk=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {"detail": "Branch not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {"detail": "You do not have a Director profile."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = get_director_dashboard(branch)
        return Response(data)


class SuperAdminDashboardView(APIView):
    """
    GET /api/v1/dashboard/super-admin/

    Returns system-wide dashboard data.
    Permission: Super Admin only.
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request: Request) -> Response:
        data = get_super_admin_dashboard()
        return Response(data)
