"""Accounts views (README Section 17)."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Account
from .permissions import IsAdminOrHigher
from .serializers import AccountSerializer


class AccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only account list/detail.

    - Admin / Director / SuperAdmin can list all accounts.
    - Auth endpoints (JWT via Telegram) to be added later.
    """

    queryset = Account.objects.prefetch_related(
        "client_profile", "staff_profile", "administrator_profile",
        "director_profile", "superadmin_profile",
    )
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    ordering_fields = ["created_at", "telegram_id"]
    ordering = ["-created_at"]
    search_fields = ["phone", "telegram_id"]
