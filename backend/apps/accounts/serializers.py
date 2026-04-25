"""
Accounts serializers.

Serializers for Account and all role tables (README Section 14.1, 14.2).
"""

import time
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.branches.models import Branch

from .models import Account, Administrator, Client, Director, Staff, SuperAdmin

# Roles a Super Admin can assign through the user-management UI.
ROLE_CHOICES = ("staff", "administrator", "director", "superadmin")
ROLES_NEEDING_BRANCH = {"staff", "administrator", "director"}

# Pairs that may be combined on a single account via `also_role`.
# Business rule (README §3.2): a Director can also serve as Administrator
# of the same branch (and vice-versa). No other dual-role combos are allowed.
DUAL_ROLE_PAIRS = {
    "director": "administrator",
    "administrator": "director",
}


def _profile_for(account: Account):
    """Return the (model, instance) for the account's primary role profile, or (None, None)."""
    for attr, model in (
        ("superadmin_profile", SuperAdmin),
        ("director_profile", Director),
        ("administrator_profile", Administrator),
        ("staff_profile", Staff),
    ):
        if hasattr(account, attr):
            return model, getattr(account, attr)
    return None, None


def _next_placeholder_telegram_id() -> int:
    """
    Generate a unique placeholder telegram_id for accounts created from the
    admin panel (no real Telegram association yet). Placeholders are negative
    so they cannot collide with genuine (positive) Telegram IDs.
    """
    # Microsecond timestamp keeps ids monotonically decreasing & unique enough.
    candidate = -int(time.time() * 1_000_000)
    while Account.objects.filter(telegram_id=candidate).exists():
        candidate -= 1
    return candidate


class AccountSerializer(serializers.ModelSerializer):
    """
    Account representation used by the Super Admin user-management UI.

    Read fields expose the account + its primary role profile (full_name,
    branch, salary). Write fields allow Super Admin to create accounts with
    a role + role-specific data, change phone/password, and toggle status.
    """

    # ---- Read-only enriched fields ----------------------------------------
    roles = serializers.ListField(read_only=True)
    role = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    branch_id = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    salary = serializers.SerializerMethodField()

    # ---- Write-only inputs (used on create / update) ----------------------
    password = serializers.CharField(
        write_only=True, required=False, min_length=6, allow_blank=False,
    )
    role_input = serializers.ChoiceField(
        write_only=True, required=False, choices=ROLE_CHOICES,
    )
    full_name_input = serializers.CharField(
        write_only=True, required=False, max_length=255,
    )
    branch = serializers.PrimaryKeyRelatedField(
        write_only=True, required=False, allow_null=True,
        queryset=Branch.objects.all(),
    )
    salary_input = serializers.DecimalField(
        write_only=True, required=False, max_digits=12, decimal_places=2,
    )
    # Dual-role flag — when role_input='director', set also_role='administrator'
    # to also create an Administrator profile on the same branch (and vice-versa).
    # On update, pass also_role=None|''  to remove any secondary profile, or
    # pass the partner role name to add it.
    also_role = serializers.ChoiceField(
        write_only=True, required=False, allow_null=True, allow_blank=True,
        choices=("director", "administrator"),
    )

    class Meta:
        model = Account
        fields = [
            # read
            "id", "telegram_id", "telegram_chat_id", "phone", "is_active",
            "roles", "role", "full_name", "branch_id", "branch_name", "salary",
            "created_at", "updated_at",
            # write
            "password", "role_input", "full_name_input", "branch", "salary_input",
            "also_role",
        ]
        read_only_fields = [
            "id", "telegram_id", "roles", "role", "full_name",
            "branch_id", "branch_name", "salary", "created_at", "updated_at",
        ]
        extra_kwargs = {
            # Phone is the login identifier — required on create, editable later.
            "phone": {"required": False, "allow_blank": True},
            "is_active": {"required": False},
            "telegram_chat_id": {"required": False, "allow_null": True},
        }

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------
    def get_role(self, obj: Account) -> str | None:
        # Highest-privilege wins (one user can hold multiple).
        for role in ("superadmin", "director", "administrator", "staff", "client"):
            if role in obj.roles:
                return role
        return None

    def get_full_name(self, obj: Account) -> str:
        _, profile = _profile_for(obj)
        return getattr(profile, "full_name", "") if profile else ""

    def get_branch_id(self, obj: Account):
        _, profile = _profile_for(obj)
        return getattr(profile, "branch_id", None) if profile else None

    def get_branch_name(self, obj: Account):
        _, profile = _profile_for(obj)
        branch = getattr(profile, "branch", None) if profile else None
        return branch.name if branch else None

    def get_salary(self, obj: Account):
        if hasattr(obj, "director_profile"):
            return str(obj.director_profile.salary)
        return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_phone(self, value: str) -> str:
        value = (value or "").strip()
        if value:
            qs = Account.objects.filter(phone=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "An account with this phone number already exists."
                )
        return value

    def validate(self, attrs):
        is_create = self.instance is None
        role = attrs.get("role_input")
        also_role = attrs.get("also_role") or None

        if is_create:
            self._validate_create_required(attrs, role)

        if also_role:
            self._validate_also_role(role, also_role)

        return attrs

    @staticmethod
    def _validate_create_required(attrs, role):
        if not role:
            raise serializers.ValidationError({"role_input": "Role is required."})
        if not attrs.get("phone"):
            raise serializers.ValidationError(
                {"phone": "Phone is required for admin-panel accounts."},
            )
        if not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "Password is required."},
            )
        if not attrs.get("full_name_input"):
            raise serializers.ValidationError(
                {"full_name_input": "Full name is required."},
            )
        if role in ROLES_NEEDING_BRANCH and not attrs.get("branch"):
            raise serializers.ValidationError(
                {"branch": f"Branch is required for {role} role."},
            )

    def _validate_also_role(self, role, also_role):
        primary = role or self._current_primary_role()
        if primary not in DUAL_ROLE_PAIRS:
            raise serializers.ValidationError({
                "also_role": "Dual roles are only available for "
                             "Director ↔ Administrator combinations.",
            })
        if DUAL_ROLE_PAIRS[primary] != also_role:
            raise serializers.ValidationError({
                "also_role": f"For a {primary} the secondary role must be "
                             f"'{DUAL_ROLE_PAIRS[primary]}'.",
            })

    def _current_primary_role(self) -> str | None:
        """Highest-privilege existing role on the instance (update flow)."""
        if self.instance is None:
            return None
        for r in ("superadmin", "director", "administrator", "staff"):
            if r in self.instance.roles:
                return r
        return None

    # ------------------------------------------------------------------
    # Create / update
    # ------------------------------------------------------------------
    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data.pop("role_input")
        full_name = validated_data.pop("full_name_input")
        branch = validated_data.pop("branch", None)
        salary = validated_data.pop("salary_input", None)
        also_role = validated_data.pop("also_role", None) or None

        account = Account(
            telegram_id=_next_placeholder_telegram_id(),
            phone=validated_data.get("phone", "").strip(),
            is_active=validated_data.get("is_active", True),
            telegram_chat_id=validated_data.get("telegram_chat_id"),
        )
        account.set_password(password)
        account.save()

        self._create_role_profile(account, role, full_name, branch, salary)
        if also_role:
            # Same branch + same name; salary only applies to director profile.
            self._create_role_profile(account, also_role, full_name, branch, salary)
        return account

    @transaction.atomic
    def update(self, instance: Account, validated_data):
        # Allow editing phone / password / is_active / chat_id and the
        # full_name + salary on the existing role profile. Role itself is
        # immutable in v1 (delete + recreate to switch roles), but the
        # secondary "also_role" can be added or removed in-place.
        password = validated_data.pop("password", None)
        full_name = validated_data.pop("full_name_input", None)
        salary = validated_data.pop("salary_input", None)
        also_role_provided = "also_role" in validated_data
        also_role = validated_data.pop("also_role", None) or None
        # role_input / branch are accepted but ignored on update for safety.
        validated_data.pop("role_input", None)
        validated_data.pop("branch", None)

        self._apply_account_fields(instance, validated_data, password)
        self._sync_profile_fields(instance, full_name, salary)

        if also_role_provided:
            primary = self._current_primary_role()
            if primary in DUAL_ROLE_PAIRS:
                self._sync_secondary_role(
                    instance, primary, also_role, full_name, salary,
                )

        return instance

    @staticmethod
    def _apply_account_fields(instance, validated_data, password):
        for field in ("phone", "is_active", "telegram_chat_id"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        if password:
            instance.set_password(password)
        instance.save()

    @classmethod
    def _sync_profile_fields(cls, instance, full_name, salary):
        for profile in cls._all_profiles(instance):
            changed = False
            if full_name is not None and hasattr(profile, "full_name"):
                profile.full_name = full_name
                changed = True
            if salary is not None and isinstance(profile, Director):
                profile.salary = Decimal(salary)
                changed = True
            if changed:
                profile.save()

    @staticmethod
    def _all_profiles(account: Account):
        result = []
        for attr in ("director_profile", "administrator_profile",
                     "staff_profile", "superadmin_profile"):
            if hasattr(account, attr):
                result.append(getattr(account, attr))
        return result

    @classmethod
    def _sync_secondary_role(cls, account, primary, also_role,
                             full_name, salary):
        """Add or remove the partner role profile based on `also_role`."""
        partner = DUAL_ROLE_PAIRS[primary]
        partner_attr = f"{partner}_profile"
        has_partner = hasattr(account, partner_attr)

        if also_role:
            if also_role != partner:
                # Validation should have caught this, but be safe.
                return
            if has_partner:
                return  # already present
            # Reuse branch from the primary profile.
            primary_profile = getattr(account, f"{primary}_profile")
            cls._create_role_profile(
                account, partner,
                full_name or primary_profile.full_name,
                primary_profile.branch,
                salary,
            )
        elif has_partner:
            getattr(account, partner_attr).delete()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _create_role_profile(account, role, full_name, branch, salary):
        if role == "superadmin":
            SuperAdmin.objects.create(account=account, full_name=full_name)
        elif role == "director":
            Director.objects.create(
                account=account,
                branch=branch,
                full_name=full_name,
                salary=Decimal(salary) if salary is not None else Decimal("2000000"),
            )
        elif role == "administrator":
            Administrator.objects.create(
                account=account, branch=branch, full_name=full_name,
            )
        elif role == "staff":
            from django.utils import timezone
            Staff.objects.create(
                account=account,
                branch=branch,
                full_name=full_name,
                hire_date=timezone.now().date(),
            )


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "account", "full_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ["id", "account", "branch", "full_name", "hire_date", "is_active"]
        read_only_fields = ["id"]


class AdministratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Administrator
        fields = ["id", "account", "branch", "full_name", "is_active"]
        read_only_fields = ["id"]


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ["id", "account", "branch", "full_name", "salary", "is_active"]
        read_only_fields = ["id"]


class SuperAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuperAdmin
        fields = ["id", "account", "full_name"]
        read_only_fields = ["id"]
