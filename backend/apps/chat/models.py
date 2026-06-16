"""
Chat models — Telegram Mini App AI assistant.

A `Conversation` belongs to one Account (the client) and holds an ordered
list of `Message` records. Messages have `role ∈ {user, assistant, system}`
and a free-form `content` string. The OpenAI proxy view appends one user
message and one assistant reply per turn.

The model intentionally does NOT store any operator user — operator/staff
takeover is a future feature; until then every assistant reply is generated
by the LLM proxy.
"""

from django.db import models


class Conversation(models.Model):
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_conversations"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conv #{self.pk} (acc:{self.account_id})"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
