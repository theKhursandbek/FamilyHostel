"""
Tests for the backup & restore system (Step 26).

Tests cover:
    - LocalBackupStorage: save, load, list, delete, exists, retention
    - Backup service: create_backup, validate_backup, cleanup_old_backups
    - Management commands: backup_db, restore_db
    - Celery tasks: daily_backup, weekly_backup
"""

import gzip
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.backups.services import (
    cleanup_old_backups,
    validate_backup,
)
from apps.backups.storage import LocalBackupStorage


# ==============================================================================
# LocalBackupStorage tests
# ==============================================================================


class TestLocalBackupStorage:
    """Tests for the local filesystem backup storage backend."""

    def test_save_and_load(self, tmp_path):
        """Save data and load it back."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            data = b"-- PostgreSQL database dump\nCREATE TABLE test;"
            storage.save("test_backup.sql", data)
            loaded = storage.load("test_backup.sql")
            assert loaded == data

    def test_save_prevents_overwrite(self, tmp_path):
        """Saving a file that already exists raises FileExistsError."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            data = b"test data"
            storage.save("dup.sql", data)
            with pytest.raises(FileExistsError):
                storage.save("dup.sql", data)

    def test_load_missing_file(self, tmp_path):
        """Loading a non-existent file raises FileNotFoundError."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            with pytest.raises(FileNotFoundError):
                storage.load("nonexistent.sql")

    def test_exists(self, tmp_path):
        """exists() returns True for saved files, False otherwise."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            assert storage.exists("nope.sql") is False
            storage.save("exists.sql", b"data")
            assert storage.exists("exists.sql") is True

    def test_delete(self, tmp_path):
        """delete() removes a file and it no longer exists."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("to_delete.sql", b"data")
            assert storage.exists("to_delete.sql") is True
            storage.delete("to_delete.sql")
            assert storage.exists("to_delete.sql") is False

    def test_delete_nonexistent_is_noop(self, tmp_path):
        """delete() on a missing file doesn't raise."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.delete("ghost.sql")  # should not raise

    def test_list_backups(self, tmp_path):
        """list_backups() returns all files sorted by name."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("daily_backup_20260401.sql", b"a")
            storage.save("daily_backup_20260402.sql", b"bb")
            storage.save("weekly_backup_20260401.sql", b"ccc")

            all_backups = storage.list_backups()
            assert len(all_backups) == 3

            daily_backups = storage.list_backups(prefix="daily_")
            assert len(daily_backups) == 2

            weekly_backups = storage.list_backups(prefix="weekly_")
            assert len(weekly_backups) == 1

    def test_list_backups_includes_size(self, tmp_path):
        """list_backups() includes file size."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("sized.sql", b"hello world")
            backups = storage.list_backups()
            assert backups[0]["size"] == 11

    def test_creates_directory_if_missing(self, tmp_path):
        """Storage backend creates the backup directory automatically."""
        backup_dir = tmp_path / "nested" / "backups"
        with override_settings(BACKUP_LOCAL_DIR=backup_dir):
            storage = LocalBackupStorage()
            assert storage.backup_dir.exists()


# ==============================================================================
# Backup validation tests
# ==============================================================================


class TestValidateBackup:
    """Tests for backup file validation."""

    def test_valid_sql_gz_backup(self, tmp_path):
        """Validates a gzipped SQL dump correctly."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            sql = b"-- PostgreSQL database dump\nCREATE TABLE accounts;"
            compressed = gzip.compress(sql)
            storage.save("valid.sql.gz", compressed)

            result = validate_backup("valid.sql.gz")
            assert result["valid"] is True
            assert result["format"] == "gzip+sql"
            assert result["error"] is None

    def test_valid_plain_sql_backup(self, tmp_path):
        """Validates a plain SQL dump correctly."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            sql = b"SET statement_timeout = 0;\nCREATE TABLE test;"
            storage.save("valid.sql", sql)

            result = validate_backup("valid.sql")
            assert result["valid"] is True
            assert result["format"] == "sql"

    def test_invalid_content(self, tmp_path):
        """Detects non-SQL content as invalid."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("bad.sql", b"this is not sql at all, just random text")

            result = validate_backup("bad.sql")
            assert result["valid"] is False

    def test_missing_file(self, tmp_path):
        """Returns invalid for non-existent file."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            result = validate_backup("ghost.sql.gz")
            assert result["valid"] is False
            assert "not found" in result["error"].lower()

    def test_corrupt_gzip(self, tmp_path):
        """Detects corrupt gzip as invalid."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("corrupt.sql.gz", b"not actually gzipped")

            result = validate_backup("corrupt.sql.gz")
            assert result["valid"] is False


# ==============================================================================
# Retention cleanup tests
# ==============================================================================


class TestCleanupOldBackups:
    """Tests for the retention policy cleanup."""

    def test_deletes_oldest_over_limit(self, tmp_path):
        """Keeps only the newest N backups."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            for i in range(10):
                storage.save(f"daily_backup_2026040{i}.sql", b"data")

            deleted = cleanup_old_backups(backup_type="daily", keep_count=3)
            assert deleted == 7

            remaining = storage.list_backups(prefix="daily_")
            assert len(remaining) == 3

    def test_no_deletion_when_under_limit(self, tmp_path):
        """No deletions when backup count is within limit."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("daily_backup_001.sql", b"data")
            storage.save("daily_backup_002.sql", b"data")

            deleted = cleanup_old_backups(backup_type="daily", keep_count=5)
            assert deleted == 0

    def test_uses_settings_retention(self, tmp_path):
        """Uses BACKUP_RETENTION from settings when keep_count not specified."""
        with override_settings(
            BACKUP_LOCAL_DIR=tmp_path,
            BACKUP_RETENTION={"daily": 2, "weekly": 1},
        ):
            storage = LocalBackupStorage()
            for i in range(5):
                storage.save(f"daily_backup_2026040{i}.sql", b"data")

            deleted = cleanup_old_backups(backup_type="daily")
            assert deleted == 3

    def test_keeps_newest_backups(self, tmp_path):
        """Oldest backups are deleted, newest are kept."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            storage.save("daily_backup_20260401.sql", b"old")
            storage.save("daily_backup_20260402.sql", b"mid")
            storage.save("daily_backup_20260403.sql", b"new")

            cleanup_old_backups(backup_type="daily", keep_count=1)

            remaining = storage.list_backups(prefix="daily_")
            assert len(remaining) == 1
            assert remaining[0]["name"] == "daily_backup_20260403.sql"

    def test_weekly_retention_separate(self, tmp_path):
        """Weekly and daily backups have independent retention."""
        with override_settings(BACKUP_LOCAL_DIR=tmp_path):
            storage = LocalBackupStorage()
            for i in range(5):
                storage.save(f"daily_backup_0{i}.sql", b"d")
                storage.save(f"weekly_backup_0{i}.sql", b"w")

            cleanup_old_backups(backup_type="daily", keep_count=2)
            cleanup_old_backups(backup_type="weekly", keep_count=3)

            assert len(storage.list_backups(prefix="daily_")) == 2
            assert len(storage.list_backups(prefix="weekly_")) == 3


# ==============================================================================
# Management command tests
# ==============================================================================


@pytest.mark.django_db
class TestBackupDbCommand:
    """Tests for the backup_db management command."""

    @patch("apps.backups.management.commands.backup_db.create_backup")
    def test_creates_daily_backup(self, mock_create):
        """Default invocation creates a daily backup."""
        mock_create.return_value = "daily_backup_20260409_120000.sql.gz"

        out = StringIO()
        call_command("backup_db", stdout=out)

        mock_create.assert_called_once_with(backup_type="daily")
        assert "daily_backup_20260409_120000.sql.gz" in out.getvalue()

    @patch("apps.backups.management.commands.backup_db.create_backup")
    def test_creates_weekly_backup(self, mock_create):
        """--type weekly creates a weekly backup."""
        mock_create.return_value = "weekly_backup_20260409_120000.sql.gz"

        out = StringIO()
        call_command("backup_db", type="weekly", stdout=out)

        mock_create.assert_called_once_with(backup_type="weekly")

    @patch("apps.backups.management.commands.backup_db.cleanup_old_backups")
    @patch("apps.backups.management.commands.backup_db.create_backup")
    def test_cleanup_flag(self, mock_create, mock_cleanup):
        """--cleanup runs retention cleanup after backup."""
        mock_create.return_value = "daily_backup_test.sql.gz"
        mock_cleanup.return_value = 3

        out = StringIO()
        call_command("backup_db", cleanup=True, stdout=out)

        mock_cleanup.assert_called_once_with(backup_type="daily")
        assert "3" in out.getvalue()


@pytest.mark.django_db
class TestRestoreDbCommand:
    """Tests for the restore_db management command."""

    @patch("apps.backups.management.commands.restore_db.get_backup_storage")
    def test_list_backups(self, mock_storage_factory):
        """--list displays available backups."""
        mock_storage = MagicMock()
        mock_storage.list_backups.return_value = [
            {"name": "daily_backup_001.sql.gz", "size": 1024, "created": None},
        ]
        mock_storage_factory.return_value = mock_storage

        out = StringIO()
        call_command("restore_db", list=True, stdout=out)

        assert "daily_backup_001.sql.gz" in out.getvalue()

    @patch("apps.backups.management.commands.restore_db.get_backup_storage")
    def test_list_empty(self, mock_storage_factory):
        """--list with no backups shows appropriate message."""
        mock_storage = MagicMock()
        mock_storage.list_backups.return_value = []
        mock_storage_factory.return_value = mock_storage

        out = StringIO()
        call_command("restore_db", list=True, stdout=out)

        assert "No backups found" in out.getvalue()

    @patch("apps.backups.management.commands.restore_db.validate_backup")
    def test_validates_before_restore(self, mock_validate):
        """Validation failure prevents restore."""
        mock_validate.return_value = {
            "valid": False,
            "error": "Does not appear to be a PostgreSQL dump",
        }

        out = StringIO()
        err = StringIO()
        with pytest.raises(Exception, match="validation failed"):
            call_command("restore_db", "bad.sql.gz", force=True, stdout=out, stderr=err)

    def test_requires_filename_or_list(self):
        """No filename and no --list raises error."""
        out = StringIO()
        err = StringIO()
        with pytest.raises(Exception, match="provide a backup filename"):
            call_command("restore_db", stdout=out, stderr=err)


# ==============================================================================
# Celery task tests
# ==============================================================================


class TestCeleryTasks:
    """Tests for the Celery backup tasks."""

    @patch("apps.backups.tasks.cleanup_old_backups", return_value=2)
    @patch("apps.backups.tasks.create_backup", return_value="daily_test.sql.gz")
    def test_daily_backup_task(self, mock_create, mock_cleanup):
        """daily_backup task creates backup and runs cleanup."""
        from apps.backups.tasks import daily_backup

        result = daily_backup()

        mock_create.assert_called_once_with(backup_type="daily")
        mock_cleanup.assert_called_once_with(backup_type="daily")
        assert result["filename"] == "daily_test.sql.gz"
        assert result["deleted"] == 2

    @patch("apps.backups.tasks.cleanup_old_backups", return_value=1)
    @patch("apps.backups.tasks.create_backup", return_value="weekly_test.sql.gz")
    def test_weekly_backup_task(self, mock_create, mock_cleanup):
        """weekly_backup task creates backup and runs cleanup."""
        from apps.backups.tasks import weekly_backup

        result = weekly_backup()

        mock_create.assert_called_once_with(backup_type="weekly")
        mock_cleanup.assert_called_once_with(backup_type="weekly")
        assert result["filename"] == "weekly_test.sql.gz"
        assert result["deleted"] == 1


# ==============================================================================
# Storage factory tests
# ==============================================================================


class TestStorageFactory:
    """Tests for the get_backup_storage() factory function."""

    def test_default_returns_local(self):
        """Default storage backend is local."""
        with override_settings(BACKUP_STORAGE_BACKEND="local"):
            from apps.backups.storage import get_backup_storage

            storage = get_backup_storage()
            assert isinstance(storage, LocalBackupStorage)

    def test_azure_without_credentials_raises(self):
        """Azure backend without azure SDK raises ValueError."""
        with override_settings(
            BACKUP_STORAGE_BACKEND="azure",
            BACKUP_AZURE_ACCOUNT_NAME="",
            BACKUP_AZURE_ACCOUNT_KEY="",
        ):
            from apps.backups.storage import get_backup_storage

            with pytest.raises(ValueError):
                get_backup_storage()


# ==============================================================================
# create_backup service tests (mocked pg_dump)
# ==============================================================================


class TestCreateBackup:
    """Tests for the create_backup service function."""

    @patch("apps.backups.services.get_backup_storage")
    @patch("subprocess.run")
    def test_creates_compressed_backup(self, mock_run, mock_storage_factory, tmp_path):
        """create_backup runs pg_dump and saves compressed output."""
        mock_run.return_value = MagicMock(
            stdout=b"-- PostgreSQL database dump\nCREATE TABLE test;",
            returncode=0,
        )
        mock_storage = MagicMock()
        mock_storage.save.return_value = "daily_backup_test.sql.gz"
        mock_storage_factory.return_value = mock_storage

        from apps.backups.services import create_backup

        filename = create_backup(backup_type="daily")

        assert filename.startswith("daily_backup_")
        assert filename.endswith(".sql.gz")
        mock_run.assert_called_once()
        mock_storage.save.assert_called_once()

        # Verify the saved data is gzip-compressed
        saved_data = mock_storage.save.call_args[0][1]
        decompressed = gzip.decompress(saved_data)
        assert b"PostgreSQL database dump" in decompressed

    @patch("apps.backups.services.get_backup_storage")
    @patch("subprocess.run")
    def test_weekly_backup_prefix(self, mock_run, mock_storage_factory):
        """Weekly backups have 'weekly_backup_' prefix."""
        mock_run.return_value = MagicMock(
            stdout=b"-- PostgreSQL database dump",
            returncode=0,
        )
        mock_storage = MagicMock()
        mock_storage.save.return_value = "ok"
        mock_storage_factory.return_value = mock_storage

        from apps.backups.services import create_backup

        filename = create_backup(backup_type="weekly")
        assert filename.startswith("weekly_backup_")
