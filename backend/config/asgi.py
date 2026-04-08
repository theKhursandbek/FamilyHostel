"""
ASGI config for Hostel Management System.

Integrates Django Channels for WebSocket support (Step 21.4).
HTTP requests are routed to the standard Django ASGI app.
WebSocket connections are handled by channel consumers via routing.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Django must be set up before importing routing.
django_asgi_app = get_asgi_application()

from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns),
    ),
})
