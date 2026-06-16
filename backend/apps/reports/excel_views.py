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

from apps.branches.models import Branch

from .dashboard_service import build_branch_dashboard
from .excel.workbook import (
    build_branch_workbook,
    list_available_workbooks,
    _can_view_branch,
)

XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Repeated 400 detail used by every endpoint that parses a ?year= path arg.
_INVALID_YEAR_MSG = "Invalid year"


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
            return Response({"detail": _INVALID_YEAR_MSG}, status=400)

        buf = build_branch_workbook(branch=branch, year=year_i, viewer=request.user)
        filename = f"branch_{branch.name}_{year_i}.xlsx".replace(" ", "_")
        resp = FileResponse(buf, as_attachment=True, filename=filename,
                            content_type=XLSX_MIME)
        return resp


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

