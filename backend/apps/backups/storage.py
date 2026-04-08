"""
Backup storage backends — local filesystem & Azure Blob Storage (Step 26).

Each backend implements:
    save(filename, data)   → str   (returns stored path/key)
    load(filename)         → bytes
    list_backups(prefix)   → list[dict]  (name, size, created)
    delete(filename)       → None
    exists(filename)       → bool
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("backups")


# ==============================================================================
# Local filesystem backend
# ==============================================================================


class LocalBackupStorage:
    """Store backups on the local filesystem."""

    def __init__(self):
        self.backup_dir = Path(
            getattr(settings, "BACKUP_LOCAL_DIR", settings.BASE_DIR / "backups")
        )
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, data: bytes) -> str:
        filepath = self.backup_dir / filename
        if filepath.exists():
            raise FileExistsError(f"Backup already exists: {filepath}")
        filepath.write_bytes(data)
        logger.info("Backup saved locally: %s (%d bytes)", filepath, len(data))
        return str(filepath)

    def load(self, filename: str) -> bytes:
        filepath = self.backup_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Backup not found: {filepath}")
        return filepath.read_bytes()

    def list_backups(self, prefix: str = "") -> list[dict]:
        backups = []
        for f in sorted(self.backup_dir.iterdir()):
            if f.is_file() and f.name.startswith(prefix):
                stat = f.stat()
                backups.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ),
                })
        return backups

    def delete(self, filename: str) -> None:
        filepath = self.backup_dir / filename
        if filepath.exists():
            filepath.unlink()
            logger.info("Backup deleted: %s", filepath)

    def exists(self, filename: str) -> bool:
        return (self.backup_dir / filename).exists()


# ==============================================================================
# Azure Blob Storage backend
# ==============================================================================


class AzureBlobBackupStorage:
    """Store backups in Azure Blob Storage container."""

    def __init__(self):
        # Lazy import — only needed when Azure is configured
        try:
            from azure.storage.blob import BlobServiceClient  # type: ignore[import-unresolved]
        except ImportError:
            raise ValueError(
                "azure-storage-blob package is not installed. "
                "Install it with: pip install azure-storage-blob"
            )

        account_name = getattr(settings, "BACKUP_AZURE_ACCOUNT_NAME", "") or os.environ.get(
            "AZURE_STORAGE_ACCOUNT_NAME", ""
        )
        account_key = getattr(settings, "BACKUP_AZURE_ACCOUNT_KEY", "") or os.environ.get(
            "AZURE_STORAGE_ACCOUNT_KEY", ""
        )
        self.container_name = getattr(
            settings, "BACKUP_AZURE_CONTAINER", "backups"
        )

        if not account_name or not account_key:
            raise ValueError(
                "Azure Blob Storage credentials not configured. "
                "Set BACKUP_AZURE_ACCOUNT_NAME and BACKUP_AZURE_ACCOUNT_KEY."
            )

        conn_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={account_name};"
            f"AccountKey={account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        self.client = BlobServiceClient.from_connection_string(conn_str)
        self.container_client = self.client.get_container_client(
            self.container_name
        )
        # Ensure container exists
        try:
            self.container_client.create_container()
        except Exception:
            pass  # Container already exists

    def save(self, filename: str, data: bytes) -> str:
        blob_client = self.container_client.get_blob_client(filename)
        if blob_client.exists():
            raise FileExistsError(f"Backup already exists in Azure: {filename}")
        blob_client.upload_blob(data)
        logger.info(
            "Backup saved to Azure Blob: %s/%s (%d bytes)",
            self.container_name,
            filename,
            len(data),
        )
        return f"{self.container_name}/{filename}"

    def load(self, filename: str) -> bytes:
        blob_client = self.container_client.get_blob_client(filename)
        if not blob_client.exists():
            raise FileNotFoundError(
                f"Backup not found in Azure: {filename}"
            )
        return blob_client.download_blob().readall()

    def list_backups(self, prefix: str = "") -> list[dict]:
        backups = []
        for blob in self.container_client.list_blobs(name_starts_with=prefix):
            backups.append({
                "name": blob.name,
                "size": blob.size,
                "created": blob.creation_time,
            })
        return sorted(backups, key=lambda b: b["name"])

    def delete(self, filename: str) -> None:
        blob_client = self.container_client.get_blob_client(filename)
        if blob_client.exists():
            blob_client.delete_blob()
            logger.info("Backup deleted from Azure: %s", filename)

    def exists(self, filename: str) -> bool:
        blob_client = self.container_client.get_blob_client(filename)
        return blob_client.exists()


# ==============================================================================
# Factory — select backend from settings
# ==============================================================================


def get_backup_storage():
    """Return the configured backup storage backend."""
    backend = getattr(settings, "BACKUP_STORAGE_BACKEND", "local")

    if backend == "azure":
        return AzureBlobBackupStorage()
    return LocalBackupStorage()
