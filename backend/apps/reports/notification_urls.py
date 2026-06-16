"""Client notifications URL config (mounted at /api/v1/notifications/)."""
from django.urls import path

from .notification_views import (
    MarkAllReadView, MarkReadView, MyNotificationsView, UnreadCountView,
)

app_name = "notifications"

urlpatterns = [
    path("my/", MyNotificationsView.as_view(), name="my"),
    path("my/unread/", UnreadCountView.as_view(), name="unread"),
    path("read_all/", MarkAllReadView.as_view(), name="read-all"),
    path("<int:pk>/read/", MarkReadView.as_view(), name="read"),
]
