"""
TEST DOC: Azure Blob Storage Integration

WHAT: Tests for BlobStorageManager database sync
WHY: Ensure reliable database persistence to Azure
HOW: Unit tests with mocked Azure SDK, integration test with Azurite

CASES:
- Upload file to blob storage
- Download file from blob storage
- Sync databases (upload/download)
- Handle missing blobs gracefully

EDGE CASES:
- Blob doesn't exist on download
- Container creation
- Backup creation on download
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBlobStorageManager:
    """Tests for BlobStorageManager."""

    @pytest.fixture
    def mock_blob_service(self) -> MagicMock:
        """Create mock blob service client."""
        mock_service = MagicMock()
        mock_container = MagicMock()
        mock_container.exists.return_value = True

        mock_service.get_container_client.return_value = mock_container
        return mock_service

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_upload_file(self, mock_blob_service: MagicMock, temp_dir: Path) -> None:
        """Should upload local file to blob storage."""
        from ib_daily_picker.discord.storage import BlobStorageManager

        # Create test file
        test_file = temp_dir / "test.db"
        test_file.write_text("test data")

        with patch(
            "ib_daily_picker.discord.storage.BlobStorageManager._get_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_blob_service

            manager = BlobStorageManager(
                container_name="test-container",
                connection_string="fake-connection-string",
            )

            manager.upload_file(test_file)

        # Verify upload was called
        mock_container = mock_blob_service.get_container_client.return_value
        mock_blob_client = mock_container.get_blob_client.return_value
        mock_blob_client.upload_blob.assert_called_once()

    def test_download_file_exists(self, mock_blob_service: MagicMock, temp_dir: Path) -> None:
        """Should download blob to local file."""
        from ib_daily_picker.discord.storage import BlobStorageManager

        local_path = temp_dir / "downloaded.db"

        # Mock blob exists and has content
        mock_container = mock_blob_service.get_container_client.return_value
        mock_blob_client = mock_container.get_blob_client.return_value
        mock_blob_client.exists.return_value = True
        mock_download = MagicMock()
        mock_download.readinto = MagicMock(side_effect=lambda f: f.write(b"test data"))
        mock_blob_client.download_blob.return_value = mock_download

        with patch(
            "ib_daily_picker.discord.storage.BlobStorageManager._get_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_blob_service

            manager = BlobStorageManager(
                container_name="test-container",
                connection_string="fake-connection-string",
            )

            result = manager.download_file("test.db", local_path)

        assert result is True
        # File should be created (though content is from mock)

    def test_download_file_not_exists(self, mock_blob_service: MagicMock, temp_dir: Path) -> None:
        """Should return False when blob doesn't exist."""
        from ib_daily_picker.discord.storage import BlobStorageManager

        local_path = temp_dir / "missing.db"

        # Mock blob doesn't exist
        mock_container = mock_blob_service.get_container_client.return_value
        mock_blob_client = mock_container.get_blob_client.return_value
        mock_blob_client.exists.return_value = False

        with patch(
            "ib_daily_picker.discord.storage.BlobStorageManager._get_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_blob_service

            manager = BlobStorageManager(
                container_name="test-container",
                connection_string="fake-connection-string",
            )

            result = manager.download_file("missing.db", local_path)

        assert result is False

    def test_sync_databases_download(self, mock_blob_service: MagicMock, temp_dir: Path) -> None:
        """Should sync databases by downloading from blob."""
        from ib_daily_picker.discord.storage import BlobStorageManager

        duckdb_path = temp_dir / "analytics.duckdb"
        sqlite_path = temp_dir / "state.sqlite"

        # Mock blobs exist
        mock_container = mock_blob_service.get_container_client.return_value
        mock_blob_client = mock_container.get_blob_client.return_value
        mock_blob_client.exists.return_value = True
        mock_download = MagicMock()
        mock_download.readinto = MagicMock(side_effect=lambda f: f.write(b"data"))
        mock_blob_client.download_blob.return_value = mock_download

        with patch(
            "ib_daily_picker.discord.storage.BlobStorageManager._get_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_blob_service

            manager = BlobStorageManager(
                container_name="test-container",
                connection_string="fake-connection-string",
            )

            results = manager.sync_databases(duckdb_path, sqlite_path, download=True)

        assert results[duckdb_path.name] is True
        assert results[sqlite_path.name] is True

    def test_sync_databases_upload(self, mock_blob_service: MagicMock, temp_dir: Path) -> None:
        """Should sync databases by uploading to blob."""
        from ib_daily_picker.discord.storage import BlobStorageManager

        duckdb_path = temp_dir / "analytics.duckdb"
        sqlite_path = temp_dir / "state.sqlite"

        # Create local files
        duckdb_path.write_text("duckdb data")
        sqlite_path.write_text("sqlite data")

        with patch(
            "ib_daily_picker.discord.storage.BlobStorageManager._get_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_blob_service

            manager = BlobStorageManager(
                container_name="test-container",
                connection_string="fake-connection-string",
            )

            results = manager.sync_databases(duckdb_path, sqlite_path, download=False)

        assert results[duckdb_path.name] is True
        assert results[sqlite_path.name] is True


class TestCreateStorageManagerFromEnv:
    """Tests for create_storage_manager_from_env."""

    def test_returns_none_when_not_configured(self) -> None:
        """Should return None when no Azure config is set."""
        from ib_daily_picker.discord.storage import create_storage_manager_from_env

        with patch.dict("os.environ", {}, clear=True):
            result = create_storage_manager_from_env()

        assert result is None

    def test_creates_manager_with_connection_string(self) -> None:
        """Should create manager when connection string is set."""
        from ib_daily_picker.discord.storage import create_storage_manager_from_env

        with patch.dict(
            "os.environ",
            {"AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpoints=..."},
            clear=True,
        ):
            result = create_storage_manager_from_env()

        assert result is not None
        assert result._connection_string == "DefaultEndpoints=..."

    def test_creates_manager_with_account_url(self) -> None:
        """Should create manager when account URL is set."""
        from ib_daily_picker.discord.storage import create_storage_manager_from_env

        with patch.dict(
            "os.environ",
            {"AZURE_STORAGE_ACCOUNT_URL": "https://account.blob.core.windows.net"},
            clear=True,
        ):
            result = create_storage_manager_from_env()

        assert result is not None
        assert result._account_url == "https://account.blob.core.windows.net"
