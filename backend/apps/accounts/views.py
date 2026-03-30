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

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
