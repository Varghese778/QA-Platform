"""Local filesystem storage provider (S3-compatible interface)."""

import logging
import os
from pathlib import Path
from typing import Optional

from artifact_storage.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LocalStorageProvider:
    """Local filesystem storage implementation."""

    def __init__(self):
        self.base_path = Path(settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage at {self.base_path}")

    def _get_artifact_path(self, project_id: str, artifact_id: str) -> Path:
        """Get the full path for an artifact."""
        return self.base_path / project_id / artifact_id

    async def write(
        self, project_id: str, artifact_id: str, data: bytes
    ) -> str:
        """
        Write artifact binary data to storage.

        Args:
            project_id: Project namespace
            artifact_id: Artifact identifier
            data: Binary data to store

        Returns:
            File path (key) for later retrieval
        """
        artifact_path = self._get_artifact_path(project_id, artifact_id)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(artifact_path, "wb") as f:
            f.write(data)

        file_size = len(data)
        logger.info(
            f"Written artifact {artifact_id} ({file_size} bytes) to {artifact_path}"
        )

        # Return relative path as "S3 key"
        return str(artifact_path.relative_to(self.base_path))

    async def read(self, project_id: str, artifact_id: str) -> bytes:
        """
        Read artifact binary data from storage.

        Args:
            project_id: Project namespace
            artifact_id: Artifact identifier

        Returns:
            Binary content
        """
        artifact_path = self._get_artifact_path(project_id, artifact_id)

        if not artifact_path.exists():
            raise FileNotFoundError(f"Artifact {artifact_id} not found")

        with open(artifact_path, "rb") as f:
            data = f.read()

        logger.info(f"Read artifact {artifact_id} ({len(data)} bytes)")
        return data

    async def delete(self, project_id: str, artifact_id: str) -> bool:
        """
        Delete artifact from storage.

        Args:
            project_id: Project namespace
            artifact_id: Artifact identifier

        Returns:
            True if deleted, False if not found
        """
        artifact_path = self._get_artifact_path(project_id, artifact_id)

        if not artifact_path.exists():
            logger.warning(f"Artifact {artifact_id} not found for deletion")
            return False

        artifact_path.unlink()
        logger.info(f"Deleted artifact {artifact_id}")

        # Cleanup empty directories
        try:
            artifact_path.parent.rmdir()
        except OSError:
            pass  # Directory not empty, that's fine

        return True

    async def exists(self, project_id: str, artifact_id: str) -> bool:
        """
        Check if artifact exists in storage.

        Args:
            project_id: Project namespace
            artifact_id: Artifact identifier

        Returns:
            True if artifact exists
        """
        artifact_path = self._get_artifact_path(project_id, artifact_id)
        return artifact_path.exists()

    async def get_size(self, project_id: str, artifact_id: str) -> int:
        """
        Get artifact size in bytes.

        Args:
            project_id: Project namespace
            artifact_id: Artifact identifier

        Returns:
            File size in bytes
        """
        artifact_path = self._get_artifact_path(project_id, artifact_id)

        if not artifact_path.exists():
            raise FileNotFoundError(f"Artifact {artifact_id} not found")

        return artifact_path.stat().st_size


def get_storage_provider() -> LocalStorageProvider:
    """Get the storage provider instance."""
    return LocalStorageProvider()
