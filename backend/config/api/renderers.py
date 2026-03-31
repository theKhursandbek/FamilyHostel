"""
Standard API response renderer (Step 20).

Wraps **successful** DRF responses in::

    {
        "success": true,
        "data": <original response data>
    }

Error responses are already wrapped by :mod:`config.api.exception_handler`,
so this renderer only touches non-error (2xx) responses.

Pagination responses (which already contain ``results``, ``count``, etc.)
are kept intact inside the ``data`` envelope.
"""

from __future__ import annotations

from rest_framework.renderers import JSONRenderer

__all__ = ["StandardJSONRenderer"]


class StandardJSONRenderer(JSONRenderer):
    """Wrap successful responses in ``{success: true, data: ...}``."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None

        if response is not None and response.status_code < 400:
            # Don't double-wrap if already wrapped (e.g. by a custom view)
            if isinstance(data, dict) and "success" in data:
                pass
            else:
                data = {"success": True, "data": data}

        return super().render(data, accepted_media_type, renderer_context)
