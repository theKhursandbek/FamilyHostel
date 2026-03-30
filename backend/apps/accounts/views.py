"""Accounts views (README Section 17)."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only account list/detail. Auth endpoints added later."""

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [AllowAny]  # TODO: restrict
