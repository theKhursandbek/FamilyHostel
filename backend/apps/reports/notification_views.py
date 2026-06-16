"""
Client-facing notifications API.

Endpoints:
    GET  /api/v1/notifications/my/           — list my notifications
    GET  /api/v1/notifications/my/unread/    — unread count + latest
    POST /api/v1/notifications/<id>/read/    — mark a single as read
    POST /api/v1/notifications/read_all/     — mark all as read
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "message", "is_read", "created_at"]
        read_only_fields = fields


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(account=request.user)[:100]
        return Response(NotificationSerializer(qs, many=True).data)


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(account=request.user, is_read=False)
        latest = qs.order_by("-created_at").first()
        return Response({
            "count": qs.count(),
            "latest": NotificationSerializer(latest).data if latest else None,
        })


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        try:
            notif = Notification.objects.get(pk=pk, account=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=["is_read", "updated_at"])
        return Response(NotificationSerializer(notif).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            account=request.user, is_read=False,
        ).update(is_read=True)
        return Response({"updated": updated})
