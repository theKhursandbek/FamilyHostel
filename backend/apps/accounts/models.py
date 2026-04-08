"""
Account models — Authentication & Role tables.

Database schema: README Section 14.1 (Accounts) & 14.2 (Role Tables).

Tables defined here:
    - accounts       (14.1 — authentication only)
    - clients        (14.2)
    - staff          (14.2)
    - administrators (14.2)
    - directors      (14.2)
    - super_admins   (14.2)

Business rule: One account can exist in multiple role tables
(e.g., director + administrator).
"""

from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import AccountManager

# Shared FK reference (avoids duplicate literal)
BRANCH_FK_REF = "branches.Branch"


# ==============================================================================
# AUTHENTICATION MODEL (README 14.1)
# ==============================================================================


class Account(AbstractBaseUser, PermissionsMixin):
    """
    Custom authentication model.

    Fields per README:
        - id (PK)             → auto BigAutoField
        - telegram_id (UNIQUE) → BigIntegerField
        - phone                → CharField
        - password (nullable)  → inherited from AbstractBaseUser
        - is_active (boolean)  → BooleanField
        - created_at           → DateTimeField
    """

    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID",
    )
    telegram_chat_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,  # noqa: DJ001 — None means 'not configured', used as sentinel
        default=None,
        verbose_name="Telegram Chat ID",
        help_text="Used for sending Telegram Bot notifications (README 26.4).",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Phone Number",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Required for Django admin access. Not the hostel 'staff' role.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountManager()

    USERNAME_FIELD = "telegram_id"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts"
        ordering = ["-created_at"]
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return f"Account #{self.pk} (tg:{self.telegram_id})"

    # ------------------------------------------------------------------
    # Role helpers — one account can exist in multiple role tables
    # ------------------------------------------------------------------

    @property
    def is_client(self) -> bool:
        return hasattr(self, "client_profile")

    @property
    def is_hostel_staff(self) -> bool:
        return hasattr(self, "staff_profile")

    @property
    def is_administrator(self) -> bool:
        return hasattr(self, "administrator_profile")

    @property
    def is_director(self) -> bool:
        return hasattr(self, "director_profile")

    @property
    def is_superadmin(self) -> bool:
        return hasattr(self, "superadmin_profile")

    @property
    def roles(self) -> list[str]:
        """Return list of active role names for this account."""
        result = []
        if self.is_superadmin:
            result.append("superadmin")
        if self.is_director:
            result.append("director")
        if self.is_administrator:
            result.append("administrator")
        if self.is_hostel_staff:
            result.append("staff")
        if self.is_client:
            result.append("client")
        return result


# ==============================================================================
# ROLE TABLES (README 14.2)
# ==============================================================================


class Client(models.Model):
    """
    Client role — guests who book rooms via Telegram.

    Fields per README:
        - id, account_id (FK), full_name, created_at
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="client_profile",
    )
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clients"
        ordering = ["-created_at"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.full_name


class Staff(models.Model):
    """
    Staff role — cleaning workers.

    Fields per README:
        - id, account_id (FK), branch_id (FK), full_name, hire_date, is_active
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    branch = models.ForeignKey(
        BRANCH_FK_REF,
        on_delete=models.CASCADE,
        related_name="staff_members",
    )
    full_name = models.CharField(max_length=255)
    hire_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "staff"
        ordering = ["-hire_date"]
        verbose_name = "Staff Member"
        verbose_name_plural = "Staff Members"

    def __str__(self):
        return self.full_name


class Administrator(models.Model):
    """
    Administrator role — manages shifts, check-in/out, cash.

    Fields per README:
        - id, account_id (FK), branch_id (FK), full_name, is_active
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="administrator_profile",
    )
    branch = models.ForeignKey(
        BRANCH_FK_REF,
        on_delete=models.CASCADE,
        related_name="administrators",
    )
    full_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "administrators"
        verbose_name = "Administrator"
        verbose_name_plural = "Administrators"

    def __str__(self):
        return self.full_name


class Director(models.Model):
    """
    Director role — 1 per branch, branch owner/operator.

    Fields per README:
        - id, account_id (FK), branch_id (FK), full_name,
          salary (default 2000000), is_active
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="director_profile",
    )
    branch = models.ForeignKey(
        BRANCH_FK_REF,
        on_delete=models.CASCADE,
        related_name="directors",
    )
    full_name = models.CharField(max_length=255)
    salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("2000000"),
        help_text="Fixed salary in UZS (default 2,000,000).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "directors"
        verbose_name = "Director"
        verbose_name_plural = "Directors"

    def __str__(self):
        return self.full_name


class SuperAdmin(models.Model):
    """
    Super Admin role — full system control.

    Fields per README:
        - id, account_id (FK), full_name
    """

    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="superadmin_profile",
    )
    full_name = models.CharField(max_length=255)

    class Meta:
        db_table = "super_admins"
        verbose_name = "Super Admin"
        verbose_name_plural = "Super Admins"

    def __str__(self):
        return self.full_name
