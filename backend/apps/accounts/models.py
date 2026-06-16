"""
Account models — Authentication & Role tables.

Database schema: README Section 14.1 (Accounts) & 14.2 (Role Tables).

Tables defined here:
    - accounts              (14.1 — authentication only)
    - clients               (14.2)
    - staff                 (14.2)
    - administrators        (14.2)
    - directors             (14.2)
    - super_admins          (14.2)

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
        null=True,  # None means 'not configured', used as sentinel  # NOSONAR
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
    language = models.CharField(
        max_length=8,
        blank=True,
        default="ru",
        verbose_name="Preferred language",
        help_text="BCP-47-ish code (ru/uz/en); used for bot push localisation.",
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
    passport_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Passport / ID document number. Required for walk-in guests; "
                  "may be blank for legacy or telegram-only clients.",
    )
    phone_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True once the client has confirmed phone ownership through the "
            "Telegram bot onboarding (contact share + OTP). Required before "
            "issuing a Mini App JWT. See TELEGRAM_MINI_APP_PLAN.md §3.1."
        ),
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Client's date of birth (collected at Mini App registration).",
    )
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
    salary_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Per-person salary override in UZS. If null, the role default from SystemSettings is used.",
    )

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
    salary_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Per-person shift-rate override in UZS. If null, the admin shift rate from SystemSettings is used.",
    )

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
          salary_override, is_active
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
    salary_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Per-person fixed monthly salary override in UZS. If null, "
            "`SystemSettings.director_fixed_salary` is used."
        ),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "directors"
        verbose_name = "Director"
        verbose_name_plural = "Directors"
        constraints = [
            models.UniqueConstraint(
                fields=["branch"],
                condition=models.Q(is_active=True),
                name="unique_active_director_per_branch",
            ),
        ]

    def __str__(self):
        return self.full_name


class SuperAdmin(models.Model):
    """
    Super Admin (CEO) role — full system control.

    Business rule: at most 2 SuperAdmins are allowed in the system.

    Fields per README:
        - id, account_id (FK), full_name
    """

    MAX_SUPERADMINS = 2

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

    def clean(self):
        super().clean()
        # Only enforce on creation — updating existing rows is fine.
        if self.pk is None:
            existing = SuperAdmin.objects.count()
            if existing >= self.MAX_SUPERADMINS:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    f"Cannot create more than {self.MAX_SUPERADMINS} SuperAdmins. "
                    f"Currently {existing} exist."
                )

    def save(self, *args, **kwargs):
        # Run validation on every save so the cap is enforced even when
        # callers bypass full_clean() (e.g. ORM .create(), serializers).
        self.full_clean()
        return super().save(*args, **kwargs)


# ==============================================================================
# OTP TOKENS — Mini App phone verification (TELEGRAM_MINI_APP_PLAN.md §4.1)
# ==============================================================================


# ==============================================================================
# OTP TOKENS — Mini App phone verification (TELEGRAM_MINI_APP_PLAN.md §4.1)
# ==============================================================================


class OtpToken(models.Model):
    """
    One-time password issued during the Telegram Mini App onboarding.

    Lifecycle:
        1. Bot or Mini App calls POST /auth/telegram/phone/start with a
           phone number → row is created with `code_hash`, `expires_at`
           (5 min from now) and an SMS is dispatched via the configured
           backend.
        2. Client submits the 6-digit code → POST /auth/telegram/phone/verify
           checks `code_hash`, marks `consumed_at`, flips
           `Client.phone_verified=True`.
        3. Codes expire after 5 minutes; at most 5 active codes per phone
           are permitted (enforced at the view layer to keep the model
           agnostic of business policy).
    """

    PURPOSE_ONBOARDING = "onboarding"
    PURPOSE_RELOGIN = "relogin"
    PURPOSE_REGISTER = "register"
    PURPOSE_CHANGE_PASSWORD = "change_password"
    PURPOSE_FORGOT_PASSWORD = "forgot_password"
    PURPOSE_CHOICES = (
        (PURPOSE_ONBOARDING, "Onboarding"),
        (PURPOSE_RELOGIN, "Re-login"),
        (PURPOSE_REGISTER, "Registration"),
        (PURPOSE_CHANGE_PASSWORD, "Change Password"),
        (PURPOSE_FORGOT_PASSWORD, "Forgot Password"),
    )

    phone = models.CharField(
        max_length=20,
        db_index=True,
        help_text="E.164-formatted phone number (+998XXXXXXXXX).",
    )
    code_hash = models.CharField(
        max_length=128,
        help_text="SHA-256 hex digest of the OTP. Plain code is never stored.",
    )
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_ONBOARDING,
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of failed verify attempts; locked after 5.",
    )
    consumed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "otp_tokens"
        ordering = ["-created_at"]
        verbose_name = "OTP Token"
        verbose_name_plural = "OTP Tokens"
        indexes = [
            models.Index(fields=["phone", "consumed_at"], name="idx_otp_phone_unused"),
        ]

    def __str__(self):
        state = "used" if self.consumed_at else "active"
        return f"OTP {self.phone} ({self.purpose}, {state})"
