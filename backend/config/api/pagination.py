"""
Custom pagination class (Step 20).

Extends DRF's ``PageNumberPagination`` so that paginated responses include
``page`` / ``page_size`` / ``total_pages`` alongside the default ``count``,
``next`` and ``previous``.

The renderer will then wrap this inside ``{success: true, data: ...}``.
"""

from __future__ import annotations

import math

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

__all__ = ["StandardPagination"]


class StandardPagination(PageNumberPagination):
    """Paginator that adds useful page metadata."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        page_size = int(self.get_page_size(self.request) or self.page_size)  # type: ignore[arg-type]
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": math.ceil(
                    self.page.paginator.count / page_size
                ),
                "page": self.page.number,
                "page_size": page_size,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
