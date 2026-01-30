"""
Azure Blob Storage integration for database persistence.

PURPOSE: Sync SQLite/DuckDB databases to Azure Blob Storage
DEPENDENCIES: azure-storage-blob, azure-identity

ARCHITECTURE NOTES:
- Downloads databases from blob storage on startup
- Uploads databases after modifications
- Uses managed identity for authentication in Azure
- Falls back to connection string for local development
"""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.storage.blob import BlobServiceClient, ContainerClient

logger = logging.getLogger(__name__)

# Default container for database files
DEFAULT_CONTAINER = "ib-picker-data"


class BlobStorageManager:
    """Manages database sync with Azure Blob Storage."""

    def __init__(
        self,
        container_name: str = DEFAULT_CONTAINER,
        connection_string: str | None = None,
        account_url: str | None = None,
    ) -> None:
        """Initialize blob storage manager.

        Args:
            container_name: Blob container name
            connection_string: Azure Storage connection string (for local dev)
            account_url: Azure Storage account URL (for managed identity)
        """
        self._container_name = container_name
        self._connection_string = connection_string
        self._account_url = account_url
        self._client: BlobServiceClient | None = None
        self._container: ContainerClient | None = None

    def _get_client(self) -> BlobServiceClient:
        """Get or create blob service client."""
        if self._client is not None:
            return self._client

        from azure.storage.blob import BlobServiceClient

        if self._connection_string:
            # Use connection string (local development)
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
            logger.info("Using connection string for blob storage")
        elif self._account_url:
            # Use managed identity (Azure deployment)
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            self._client = BlobServiceClient(
                account_url=self._account_url,
                credential=credential,
            )
            logger.info("Using managed identity for blob storage")
        else:
            raise ValueError("Either connection_string or account_url must be provided")

        return self._client

    def _get_container(self) -> ContainerClient:
        """Get or create container client."""
        if self._container is not None:
            return self._container

        client = self._get_client()
        self._container = client.get_container_client(self._container_name)

        # Create container if it doesn't exist
        if not self._container.exists():
            self._container.create_container()
            logger.info(f"Created container: {self._container_name}")

        return self._container

    def upload_file(
        self,
        local_path: Path,
        blob_name: str | None = None,
        overwrite: bool = True,
    ) -> str:
        """Upload a file to blob storage.

        Args:
            local_path: Local file path
            blob_name: Name in blob storage (defaults to filename)
            overwrite: Whether to overwrite existing blob

        Returns:
            Blob URL
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        container = self._get_container()
        blob_name = blob_name or local_path.name

        blob_client = container.get_blob_client(blob_name)

        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=overwrite)

        logger.info(f"Uploaded {local_path} to {blob_name}")
        return blob_client.url

    def download_file(
        self,
        blob_name: str,
        local_path: Path,
        create_backup: bool = True,
    ) -> bool:
        """Download a file from blob storage.

        Args:
            blob_name: Name in blob storage
            local_path: Local destination path
            create_backup: Create backup of existing local file

        Returns:
            True if file was downloaded, False if blob doesn't exist
        """
        container = self._get_container()
        blob_client = container.get_blob_client(blob_name)

        if not blob_client.exists():
            logger.info(f"Blob {blob_name} does not exist")
            return False

        # Create backup if local file exists
        if create_backup and local_path.exists():
            backup_path = local_path.with_suffix(
                f".backup.{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
            )
            shutil.copy2(local_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Download
        with open(local_path, "wb") as f:
            download_stream = blob_client.download_blob()
            download_stream.readinto(f)

        logger.info(f"Downloaded {blob_name} to {local_path}")
        return True

    def sync_databases(
        self,
        duckdb_path: Path,
        sqlite_path: Path,
        download: bool = True,
    ) -> dict[str, bool]:
        """Sync database files with blob storage.

        Args:
            duckdb_path: Path to DuckDB database
            sqlite_path: Path to SQLite database
            download: If True, download from blob; if False, upload to blob

        Returns:
            Dict mapping filename to success status
        """
        results: dict[str, bool] = {}

        for path in [duckdb_path, sqlite_path]:
            try:
                if download:
                    # Download from blob to local
                    success = self.download_file(path.name, path)
                    results[path.name] = success
                else:
                    # Upload from local to blob
                    if path.exists():
                        self.upload_file(path)
                        results[path.name] = True
                    else:
                        logger.warning(f"Local file not found: {path}")
                        results[path.name] = False
            except Exception as e:
                logger.error(f"Error syncing {path.name}: {e}")
                results[path.name] = False

        return results

    def list_blobs(self, prefix: str | None = None) -> list[str]:
        """List blobs in the container.

        Args:
            prefix: Optional prefix filter

        Returns:
            List of blob names
        """
        container = self._get_container()
        blobs = container.list_blobs(name_starts_with=prefix)
        return [blob.name for blob in blobs]

    def delete_blob(self, blob_name: str) -> bool:
        """Delete a blob.

        Args:
            blob_name: Name of blob to delete

        Returns:
            True if deleted, False if didn't exist
        """
        container = self._get_container()
        blob_client = container.get_blob_client(blob_name)

        if not blob_client.exists():
            return False

        blob_client.delete_blob()
        logger.info(f"Deleted blob: {blob_name}")
        return True


def create_storage_manager_from_env() -> BlobStorageManager | None:
    """Create storage manager from environment variables.

    Environment variables:
        AZURE_STORAGE_CONNECTION_STRING: Connection string (local dev)
        AZURE_STORAGE_ACCOUNT_URL: Account URL (managed identity)
        AZURE_STORAGE_CONTAINER: Container name (optional)

    Returns:
        BlobStorageManager or None if not configured
    """
    import os

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER", DEFAULT_CONTAINER)

    if not connection_string and not account_url:
        logger.info("Azure Storage not configured, using local storage only")
        return None

    return BlobStorageManager(
        container_name=container_name,
        connection_string=connection_string,
        account_url=account_url,
    )
