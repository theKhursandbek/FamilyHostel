"""
Excel workbook download endpoints + monthly salary-adjustment CRUD.

Mounted under /api/v1/reports/.
"""

from __future__ import annotations

import datetime as dt

from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Director
from apps.branches.models import Branch

from .dashboard_service import build_branch_dashboard
from .excel.workbook import (
    build_branch_workbook,
    build_lobar_workbook,
    list_available_workbooks,
    _can_view_branch,
    _can_view_lobar,
)

XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _current_year() -> int:
    return dt.date.today().year


def _years_window() -> list[int]:
    y = _current_year()
    return [y - 1, y, y + 1]


class WorkbookListView(APIView):
    """GET /reports/workbook/available/ → list[{kind,branch_id,...,year}]"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = list_available_workbooks(request.user, years=_years_window())
        return Response({"results": items})


class WorkbookBranchView(APIView):
    """GET /reports/workbook/branch/<branch_id>/<year>/ → xlsx stream"""
    permission_classes = [IsAuthenticated]

    def get(self, request, branch_id: int, year: int):
        try:
            branch = Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist as exc:
            raise Http404("Branch not found") from exc
        if not _can_view_branch(request.user, branch):
            return Response({"detail": "Forbidden"}, status=403)
        try:
            year_i = int(year)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year"}, status=400)

        buf = build_branch_workbook(branch=branch, year=year_i, viewer=request.user)
        filename = f"branch_{branch.name}_{year_i}.xlsx".replace(" ", "_")
        resp = FileResponse(buf, as_attachment=True, filename=filename,
                            content_type=XLSX_MIME)
        return resp


class WorkbookGeneralManagerView(APIView):
    """GET /reports/workbook/general-manager/<director_id>/<year>/ → xlsx

    Per REFACTOR_PLAN_2026_04 §4.3 + Q7 — generalises the legacy
    ``workbook/lobar/`` endpoint so any Director with
    ``is_general_manager=True`` (and the CEO) can download a GM-flavoured
    yearly workbook tagged to that director's name.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, director_id: int, year: int):
        try:
            director = Director.objects.select_related("account").get(pk=director_id)
        except Director.DoesNotExist as exc:
            raise Http404("Director not found") from exc
        if not director.is_general_manager:
            return Response(
                {"detail": "This director is not a General Manager."},
                status=403,
            )
        # CEO sees any GM workbook; otherwise only the GM themselves.
        user = request.user
        is_self = (
            getattr(user, "director_profile", None)
            and user.director_profile.pk == director.pk
        )
        if not (user.is_superadmin or is_self):
            return Response({"detail": "Forbidden"}, status=403)

        try:
            year_i = int(year)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year"}, status=400)

        buf = build_lobar_workbook(year=year_i, viewer=request.user)
        # Q7 filename: gm_<FullName_with_underscores>_<Year>.xlsx
        safe_name = (director.full_name or f"director_{director.pk}").replace(" ", "_")
        filename = f"gm_{safe_name}_{year_i}.xlsx"
        return FileResponse(buf, as_attachment=True, filename=filename,
                            content_type=XLSX_MIME)


class WorkbookLobarView(APIView):
    """DEPRECATED — kept temporarily for backwards compatibility.

    Use ``WorkbookGeneralManagerView`` instead. This endpoint resolves the
    first GM director and proxies to the new behaviour so any old client
    URLs keep working until the cleanup pass.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, year: int):
        if not _can_view_lobar(request.user):
            return Response({"detail": "Forbidden"}, status=403)
        try:
            year_i = int(year)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year"}, status=400)
        gm = (
            Director.objects.filter(is_general_manager=True, is_active=True)
            .order_by("pk").first()
        )
        if gm is None:
            return Response(
                {"detail": "No General Manager configured."},
                status=404,
            )
        buf = build_lobar_workbook(year=year_i, viewer=request.user)
        safe_name = (gm.full_name or f"director_{gm.pk}").replace(" ", "_")
        filename = f"gm_{safe_name}_{year_i}.xlsx"
        return FileResponse(buf, as_attachment=True, filename=filename,
                            content_type=XLSX_MIME)


class BranchDashboardView(APIView):
    """GET /reports/branch-dashboard/?branch=<id>&year=<y>&month=<m>

    In-page report payload (REFACTOR_PLAN_2026_04 §4.2). Coverage matches
    the per-month workbook — KPIs, income matrix, expense breakdown,
    penalties, salary roster, cash sessions.

    Permissions:
      * SuperAdmin: any branch.
      * Director / Administrator / Staff: own branch only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        branch_raw = params.get("branch") or params.get("branch_id")
        if not branch_raw:
            return Response(
                {"detail": "branch is required."}, status=400,
            )
        try:
            branch_id = int(branch_raw)
            year = int(params.get("year") or _current_year())
            month = int(params.get("month") or dt.date.today().month)
        except (TypeError, ValueError):
            return Response(
                {"detail": "branch, year, month must be integers."},
                status=400,
            )
        if not (1 <= month <= 12):
            return Response({"detail": "month must be 1–12."}, status=400)

        try:
            branch = Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist as exc:
            raise Http404("Branch not found") from exc

        if not _can_view_branch(request.user, branch):
            return Response({"detail": "Forbidden"}, status=403)

        return Response(build_branch_dashboard(
            branch=branch, year=year, month=month,
        ))

