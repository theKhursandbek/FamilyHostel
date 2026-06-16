"""
Lightweight client-side telemetry sink.

POST ``/api/v1/metrics/web-vitals/`` with a JSON body produced by the
``web-vitals`` library:

    {"name": "LCP", "value": 1234.5, "id": "v3-1700000000000-1234567890"}

The endpoint is intentionally cheap, anonymous (AllowAny), aggressively
throttled, and only logs to the structured logger — no DB writes. A real
deployment can pipe these logs to Loki/Datadog/Sentry Performance.
"""

from __future__ import annotations

import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger("metrics.web_vitals")


class _WebVitalsThrottle(AnonRateThrottle):
    rate = "120/min"


class WebVitalsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [_WebVitalsThrottle]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        name = str(body.get("name", ""))[:32]
        value = body.get("value")
        rid = str(body.get("id", ""))[:64]
        rating = str(body.get("rating", ""))[:16]
        navtype = str(body.get("navigationType", ""))[:16]
        try:
            value_f = float(value) if value is not None else None
        except (TypeError, ValueError):
            value_f = None
        logger.info(
            "web-vitals name=%s value=%.2f rating=%s nav=%s id=%s",
            name, value_f if value_f is not None else -1.0, rating, navtype, rid,
        )
        return Response({"ok": True})
