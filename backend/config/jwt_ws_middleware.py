"""
JWT authentication middleware for WebSocket connections.

The Mini App passes the access token via ``?token=<jwt>`` query string
because browsers cannot set Authorization headers on WebSocket handshakes.

Falls through to ``AnonymousUser`` if the token is missing/invalid; the
consumer is responsible for closing unauthorised connections.
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


@database_sync_to_async
def _resolve_user(token: str):
    try:
        from rest_framework_simplejwt.tokens import UntypedToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from django.contrib.auth import get_user_model

        UntypedToken(token)  # raises on bad/expired
        validated = UntypedToken(token)
        user_id = validated.payload.get("user_id")
        if not user_id:
            return AnonymousUser()
        User = get_user_model()
        return User.objects.filter(pk=user_id, is_active=True).first() or AnonymousUser()
    except (InvalidToken, TokenError, Exception) as exc:  # pragma: no cover
        logger.debug("WS JWT rejected: %s", exc)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Resolve scope['user'] from a ``?token=`` query-string JWT."""

    async def __call__(self, scope, receive, send):
        try:
            qs = parse_qs(scope.get("query_string", b"").decode())
            token_list = qs.get("token") or []
            if token_list:
                scope["user"] = await _resolve_user(token_list[0])
        except Exception:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Drop-in replacement for ``AuthMiddlewareStack`` that also reads JWTs."""
    from channels.auth import AuthMiddlewareStack
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
