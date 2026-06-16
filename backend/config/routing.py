"""
WebSocket URL routing (Step 21.4).

Maps WebSocket paths to their respective consumers:
    /ws/admin/        → AdminDashboardConsumer
    /ws/director/     → DirectorDashboardConsumer
    /ws/super-admin/  → SuperAdminConsumer
    /ws/client/       → ClientConsumer
    /ws/staff/        → StaffConsumer
"""

from django.urls import path

from config.consumers import (
    AdminDashboardConsumer,
    DirectorDashboardConsumer,
    SuperAdminConsumer,
)
from config.user_consumers import ClientConsumer, StaffConsumer

websocket_urlpatterns = [
    path("ws/admin/", AdminDashboardConsumer.as_asgi()),
    path("ws/director/", DirectorDashboardConsumer.as_asgi()),
    path("ws/super-admin/", SuperAdminConsumer.as_asgi()),
    path("ws/client/", ClientConsumer.as_asgi()),
    path("ws/staff/", StaffConsumer.as_asgi()),
]
