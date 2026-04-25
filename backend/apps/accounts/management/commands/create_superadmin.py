"""
Provision a real, persisted SuperAdmin (CEO) account.

Usage:
    python manage.py create_superadmin \
        --phone "+998908294313" \
        --full-name "Khursandbek Saidov" \
        --password "1L0veMyself"

Behavior:
    * Idempotent — if an Account with the given phone already exists, its
      password / full_name are updated and a SuperAdmin profile is attached
      (if missing). No duplicate Account is ever created.
    * Enforces the SuperAdmin.MAX_SUPERADMINS cap (currently 2).
    * Generates a synthetic, deterministic negative `telegram_id` from the
      phone number when the account is brand new and no --telegram-id is
      supplied. This keeps the unique constraint satisfied for CEOs who
      log in via phone+password rather than Telegram.
"""

from __future__ import annotations

import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Account, SuperAdmin


def _synthetic_telegram_id(phone: str) -> int:
    """Deterministic negative int derived from phone (avoids clashes with real TG IDs)."""
    digest = hashlib.sha256(phone.encode("utf-8")).digest()
    # Take 7 bytes → fits comfortably in a signed 64-bit int, then negate.
    value = int.from_bytes(digest[:7], "big")
    return -(value or 1)


class Command(BaseCommand):
    help = "Create or update a SuperAdmin (CEO) account. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True, help="E.164 phone, e.g. +998908294313")
        parser.add_argument("--full-name", required=True, help='Full name, e.g. "Khursandbek Saidov"')
        parser.add_argument("--password", required=True, help="Plain-text password (will be hashed)")
        parser.add_argument(
            "--telegram-id",
            type=int,
            default=None,
            help="Optional Telegram ID; if omitted a deterministic synthetic value is used.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        phone: str = opts["phone"].strip()
        full_name: str = opts["full_name"].strip()
        password: str = opts["password"]
        explicit_tg_id: int | None = opts["telegram_id"]

        if not phone.startswith("+"):
            raise CommandError("Phone must be in E.164 format (start with '+').")
        if not full_name:
            raise CommandError("Full name cannot be empty.")
        if len(password) < 6:
            raise CommandError("Password must be at least 6 characters.")

        account = Account.objects.filter(phone=phone).first()
        created_account = False

        if account is None:
            telegram_id = explicit_tg_id if explicit_tg_id is not None else _synthetic_telegram_id(phone)
            # Avoid colliding with an existing telegram_id (extremely unlikely but safe).
            while Account.objects.filter(telegram_id=telegram_id).exists():
                telegram_id -= 1

            account = Account(
                phone=phone,
                telegram_id=telegram_id,
                is_active=True,
                is_staff=True,  # allows django-admin access for the CEO
            )
            account.set_password(password)
            account.save()
            created_account = True
            self.stdout.write(self.style.SUCCESS(
                f"  [OK] Created Account #{account.pk} (phone={phone}, telegram_id={telegram_id})"
            ))
        else:
            account.set_password(password)
            if not account.is_active:
                account.is_active = True
            account.is_staff = True
            account.save()
            self.stdout.write(self.style.WARNING(
                f"  [~] Account #{account.pk} already existed - password & flags updated."
            ))

        # Attach / update SuperAdmin profile.
        profile = SuperAdmin.objects.filter(account=account).first()
        if profile is None:
            # Pre-flight cap check so we fail with a friendly message rather
            # than an opaque ValidationError from model.clean().
            current = SuperAdmin.objects.count()
            if current >= SuperAdmin.MAX_SUPERADMINS:
                raise CommandError(
                    f"Cannot create more than {SuperAdmin.MAX_SUPERADMINS} SuperAdmins "
                    f"(currently {current}). Delete one first or update an existing CEO."
                )
            profile = SuperAdmin.objects.create(account=account, full_name=full_name)
            self.stdout.write(self.style.SUCCESS(
                f"  [OK] Created SuperAdmin profile #{profile.pk} ({full_name})"
            ))
        else:
            if profile.full_name != full_name:
                profile.full_name = full_name
                profile.save()
                self.stdout.write(self.style.WARNING(
                    f"  [~] SuperAdmin profile #{profile.pk} renamed to {full_name}"
                ))
            else:
                self.stdout.write(
                    f"  [-] SuperAdmin profile #{profile.pk} already up-to-date."
                )

        action = "Created" if created_account else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"\n{action} CEO account: {full_name} ({phone}). "
            f"SuperAdmins now in system: {SuperAdmin.objects.count()}/{SuperAdmin.MAX_SUPERADMINS}"
        ))
