"""
Management command: restore_db (Step 26).

Restores a PostgreSQL database from a backup file stored in the
configured backup storage backend.

Usage:
    python manage.py restore_db daily_backup_20260409_120000.sql.gz
    python manage.py restore_db daily_backup_20260409_120000.sql.gz --no-validate
    python manage.py restore_db --list
"""

from django.core.management.base import BaseCommand, CommandError

from apps.backups.services import restore_backup, validate_backup
from apps.backups.storage import get_backup_storage


class Command(BaseCommand):
    help = "Restore a PostgreSQL database from a backup file."

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            nargs="?",
            help="Name of the backup file to restore.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all available backups.",
        )
        parser.add_argument(
            "--no-validate",
            action="store_true",
            help="Skip backup validation before restore.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt.",
        )

    def handle(self, *args, **options):
        if options["list"]:
            return self._list_backups()

        filename = options["filename"]
        if not filename:
            raise CommandError(
                "Please provide a backup filename, or use --list to see available backups."
            )

        # Validate backup before restoring
        if not options["no_validate"]:
            self.stdout.write(f"Validating backup: {filename}...")
            result = validate_backup(filename)
            if not result["valid"]:
                raise CommandError(
                    f"❌ Backup validation failed: {result.get('error', 'Unknown error')}"
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Valid backup: {result['format']}, "
                    f"{result['size_compressed']:,} bytes compressed, "
                    f"{result['size_raw']:,} bytes raw"
                )
            )

        # Confirmation prompt
        if not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  This will restore '{filename}' into the current database.\n"
                    "   Existing data may be overwritten.\n"
                )
            )
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                self.stdout.write("Restore cancelled.")
                return

        self.stdout.write(f"Restoring database from: {filename}...")

        try:
            restore_backup(filename)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Database restored from: {filename}")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Restore failed: {e}"))
            raise

    def _list_backups(self):
        """Display all available backups."""
        storage = get_backup_storage()
        backups = storage.list_backups()

        if not backups:
            self.stdout.write("No backups found.")
            return

        self.stdout.write(f"\n{'Name':<50} {'Size':>12} {'Created'}")
        self.stdout.write("-" * 85)
        for b in backups:
            size = f"{b['size']:,} B"
            created = (
                b["created"].strftime("%Y-%m-%d %H:%M:%S")
                if b["created"]
                else "N/A"
            )
            self.stdout.write(f"{b['name']:<50} {size:>12} {created}")

        self.stdout.write(f"\nTotal: {len(backups)} backup(s)")
