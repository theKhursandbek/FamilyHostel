"""
Backup service — core logic for backup/restore operations (Step 26).

Handles pg_dump/pg_restore, retention cleanup, and validation.
"""

import gzip
import logging
import subprocess
from datetime import datetime, timezone

from django.conf import settings

from apps.backups.storage import get_backup_storage

logger = logging.getLogger("backups")


def _get_db_config() -> dict:
    """Extract database connection config from Django settings."""
    db = settings.DATABASES["default"]
    return {
        "name": db["NAME"],
        "user": db["USER"],
        "password": db["PASSWORD"],
        "host": db["HOST"],
        "port": str(db["PORT"]),
    }


def create_backup(backup_type: str = "daily") -> str:
    """
    Create a compressed PostgreSQL backup via pg_dump.

    Args:
        backup_type: 'daily' or 'weekly' — used for filename prefix and retention.

    Returns:
        The filename of the stored backup.

    Raises:
        subprocess.CalledProcessError: If pg_dump fails.
    """
    db = _get_db_config()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{backup_type}_backup_{timestamp}.sql.gz"

    logger.info(
        "Starting %s backup of database '%s' → %s",
        backup_type,
        db["name"],
        filename,
    )

    env = {
        "PGPASSWORD": db["password"],
        "PATH": "/usr/bin:/usr/local/bin:/bin",
    }

    result = subprocess.run(
        [
            "pg_dump",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["name"],
            "--no-owner",
            "--no-privileges",
            "--format=plain",
        ],
        capture_output=True,
        env=env,
        check=True,
        timeout=600,  # 10 minute timeout
    )

    compressed = gzip.compress(result.stdout, compresslevel=9)
    storage = get_backup_storage()
    stored_path = storage.save(filename, compressed)

    logger.info(
        "Backup complete: %s (%d bytes raw → %d bytes compressed)",
        stored_path,
        len(result.stdout),
        len(compressed),
    )

    return filename


def restore_backup(filename: str) -> None:
    """
    Restore a PostgreSQL backup via psql.

    Args:
        filename: Name of the backup file to restore.

    Raises:
        FileNotFoundError: If the backup file doesn't exist.
        subprocess.CalledProcessError: If psql restore fails.
    """
    db = _get_db_config()
    storage = get_backup_storage()

    if not storage.exists(filename):
        raise FileNotFoundError(f"Backup file not found: {filename}")

    logger.info("Starting restore of '%s' → database '%s'", filename, db["name"])

    data = storage.load(filename)

    # Decompress if gzipped
    if filename.endswith(".gz"):
        data = gzip.decompress(data)

    env = {
        "PGPASSWORD": db["password"],
        "PATH": "/usr/bin:/usr/local/bin:/bin",
    }

    result = subprocess.run(
        [
            "psql",
            "-h", db["host"],
            "-p", db["port"],
            "-U", db["user"],
            "-d", db["name"],
            "--single-transaction",
        ],
        input=data,
        capture_output=True,
        env=env,
        check=True,
        timeout=600,
    )

    logger.info("Restore complete: %s → '%s'", filename, db["name"])

    if result.stderr:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        logger.warning("Restore warnings: %s", stderr_text[:500])


def validate_backup(filename: str) -> dict:
    """
    Validate a backup file without restoring it.

    Returns:
        dict with 'valid', 'filename', 'size', 'format' keys.
    """
    storage = get_backup_storage()

    if not storage.exists(filename):
        return {"valid": False, "error": f"File not found: {filename}"}

    data = storage.load(filename)
    is_gzipped = filename.endswith(".gz")

    try:
        if is_gzipped:
            raw = gzip.decompress(data)
        else:
            raw = data
    except gzip.BadGzipFile:
        return {"valid": False, "error": "Invalid gzip archive"}

    # Check for SQL content markers
    text = raw[:2048].decode("utf-8", errors="replace")
    has_sql = any(
        marker in text
        for marker in ("PostgreSQL database dump", "CREATE", "INSERT", "SET ")
    )

    return {
        "valid": has_sql,
        "filename": filename,
        "size_compressed": len(data),
        "size_raw": len(raw),
        "format": "gzip+sql" if is_gzipped else "sql",
        "error": None if has_sql else "Does not appear to be a PostgreSQL dump",
    }


def cleanup_old_backups(
    backup_type: str = "daily",
    keep_count: int | None = None,
) -> int:
    """
    Delete old backups exceeding the retention policy.

    Args:
        backup_type: 'daily' or 'weekly'.
        keep_count: Override number to keep (default from settings).

    Returns:
        Number of backups deleted.
    """
    if keep_count is None:
        retention: dict[str, int] = getattr(settings, "BACKUP_RETENTION", {})
        default = 7 if backup_type == "daily" else 4
        keep_count = int(retention.get(backup_type, default))

    storage = get_backup_storage()
    prefix = f"{backup_type}_backup_"
    backups = storage.list_backups(prefix=prefix)

    if len(backups) <= keep_count:
        logger.info(
            "Retention OK: %d %s backups (keep %d)",
            len(backups),
            backup_type,
            keep_count,
        )
        return 0

    # Delete oldest backups (list is sorted by name = chronological)
    to_delete = backups[: len(backups) - keep_count]
    for backup in to_delete:
        storage.delete(backup["name"])

    logger.info(
        "Retention cleanup: deleted %d old %s backups (kept %d)",
        len(to_delete),
        backup_type,
        keep_count,
    )
    return len(to_delete)
