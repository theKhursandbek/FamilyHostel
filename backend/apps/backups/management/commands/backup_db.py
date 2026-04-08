"""
Management command: backup_db (Step 26).

Creates a compressed PostgreSQL backup and stores it via the configured
backup storage backend (local or Azure Blob).

Usage:
    python manage.py backup_db
    python manage.py backup_db --type weekly
    python manage.py backup_db --cleanup
"""

from django.core.management.base import BaseCommand

from apps.backups.services import cleanup_old_backups, create_backup


class Command(BaseCommand):
    help = "Create a compressed PostgreSQL database backup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["daily", "weekly"],
            default="daily",
            help="Backup type — affects filename prefix and retention policy (default: daily).",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Run retention cleanup after creating the backup.",
        )

    def handle(self, *args, **options):
        backup_type = options["type"]

        self.stdout.write(f"Creating {backup_type} database backup...")

        try:
            filename = create_backup(backup_type=backup_type)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Backup created: {filename}")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Backup failed: {e}"))
            raise

        if options["cleanup"]:
            deleted = cleanup_old_backups(backup_type=backup_type)
            if deleted:
                self.stdout.write(f"🗑️  Deleted {deleted} old {backup_type} backup(s).")
            else:
                self.stdout.write("✅ No old backups to clean up.")
