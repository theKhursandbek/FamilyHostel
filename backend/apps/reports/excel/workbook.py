"""
Workbook orchestration — builds the 12-sheet xlsx ready to stream to client.
"""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook

from apps.accounts.models import Account, Administrator
from apps.branches.models import Branch

from .data import build_month_data
from .layout import MONTH_NAMES_RU, build_month_sheet


# ──────────────────────────────────────────────────────────────────────────────
# Viewer name resolution
# ──────────────────────────────────────────────────────────────────────────────


def _viewer_name_for(account: Account) -> str:
    """
    Returns the viewer token used for masking in ``layout._can_see``.

    - SuperAdmin (CEO) → 'CEO' so they see every column.
    - Director → 'CEO' (full visibility for the branch operator).
    - Administrator → that admin's own ``full_name``.
    - Anyone else → '' (no admin column visible).
    """
    if getattr(account, "is_superadmin", False):
        return "CEO"
    if getattr(account, "is_director", False):
        return "CEO"
    admin = Administrator.objects.filter(account=account).first()
    if admin:
        return admin.full_name
    return ""


def _can_view_branch(account: Account, branch: Branch) -> bool:
    if account.is_superadmin or account.is_director:
        return True
    for prof_attr in ("administrator_profile", "staff_profile", "director_profile"):
        prof = getattr(account, prof_attr, None)
        if prof and getattr(prof, "branch_id", None) == branch.id:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Workbook builders
# ──────────────────────────────────────────────────────────────────────────────


def build_branch_workbook(*, branch: Branch, year: int, viewer: Account) -> BytesIO:
    viewer_name = _viewer_name_for(viewer)
    wb = Workbook()
    wb.remove(wb.active)
    for m in range(1, 13):
        ws = wb.create_sheet(title=MONTH_NAMES_RU[m - 1])
        data = build_month_data(
            branch=branch, year=year, month=m, viewer_name=viewer_name,
        )
        build_month_sheet(ws, data)
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Listing what the viewer is allowed to download
# ──────────────────────────────────────────────────────────────────────────────


def list_available_workbooks(viewer: Account, *, years: Iterable[int]) -> list[dict]:
    """
    Returns a flat list of branch workbooks the viewer is entitled to download.

    Each row has ``kind="branch"`` plus ``branch_id``, ``year``, display name
    and ``can_download``.
    """
    items: list[dict] = []
    branches = Branch.objects.all()
    for branch in branches:
        if not _can_view_branch(viewer, branch):
            continue
        for y in years:
            items.append({
                "kind": "branch",
                "branch_id": branch.id,
                "branch_name": branch.name,
                "year": y,
                "can_download": True,
            })
    return items
