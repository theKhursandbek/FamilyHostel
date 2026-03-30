"""
Custom manager for the Account model.

Account uses telegram_id as USERNAME_FIELD (README Section 14.1).
"""

from django.contrib.auth.models import BaseUserManager


class AccountManager(BaseUserManager):
    """Manager for Account model — Telegram-first authentication."""

    def create_user(self, telegram_id, password=None, **extra_fields):
        """
        Create and return a regular account.

        Args:
            telegram_id: Unique Telegram user ID.
            password: Optional password (nullable per README).
        """
        if telegram_id is None:
            raise ValueError("Account must have a telegram_id.")

        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        account = self.model(telegram_id=telegram_id, **extra_fields)
        if password:
            account.set_password(password)
        else:
            account.set_unusable_password()
        account.save(using=self._db)
        return account

    def create_superuser(self, telegram_id, password=None, **extra_fields):
        """
        Create and return a superuser account (for Django admin access).
        """
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(telegram_id, password, **extra_fields)
