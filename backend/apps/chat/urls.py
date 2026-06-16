from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet

app_name = "chat"

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    path("", include(router.urls)),
]
