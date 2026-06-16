from __future__ import annotations

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .llm import ChatRateLimited, generate_reply
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


class _SendInput(serializers.Serializer):
    content = serializers.CharField(max_length=2000)


class ConversationViewSet(viewsets.ModelViewSet):
    """Mini App chat conversations.

    The caller can only see / mutate their own conversations.

        GET    /chat/conversations/                — list mine
        POST   /chat/conversations/                — create new
        GET    /chat/conversations/{id}/           — detail with messages
        DELETE /chat/conversations/{id}/           — delete
        POST   /chat/conversations/{id}/send/      — append user msg + AI reply
    """

    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_throttles(self):
        from rest_framework.throttling import ScopedRateThrottle
        # Only the heavy `send` action gets the chat scope.
        if getattr(self, "action", None) == "send":
            self.throttle_scope = "chat_user"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return (
            Conversation.objects
            .filter(account=self.request.user)
            .prefetch_related("messages")
        )

    def perform_create(self, serializer):
        serializer.save(account=self.request.user)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        conv = self.get_object()
        serializer = _SendInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["content"].strip()
        if not text:
            return Response({"detail": "Empty message."}, status=400)

        # Save user message
        user_msg = Message.objects.create(
            conversation=conv, role=Message.Role.USER, content=text,
        )

        # Build history for the LLM
        history = [
            {"role": m.role, "content": m.content}
            for m in conv.messages.order_by("created_at")
        ]

        # Generate reply
        try:
            reply, suggestions = generate_reply(conv.account_id, history)
        except ChatRateLimited as exc:
            return Response(
                {"detail": f"Rate limit hit ({exc.scope}). Please wait."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        ai_msg = Message.objects.create(
            conversation=conv, role=Message.Role.ASSISTANT, content=reply,
        )

        # Bump conversation updated_at
        conv.save(update_fields=["updated_at"])

        return Response({
            "user": MessageSerializer(user_msg).data,
            "assistant": MessageSerializer(ai_msg).data,
            "suggestions": suggestions,
        }, status=status.HTTP_201_CREATED)
