"""Mock Virus Scanner - reads Redis queue and scans artifacts."""

import asyncio
import json
import logging
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifact_storage.config import get_settings
from artifact_storage.models import ArtifactRecord
from artifact_storage.schemas.enums import ScanStatus, ArtifactStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class VirusScanner:
    """Mock virus scanner that processes Redis queue."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis: redis.Redis = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await redis.from_url(settings.redis_url)
        logger.info("Virus scanner connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Virus scanner disconnected from Redis")

    async def enqueue_scan(self, project_id: UUID, artifact_id: UUID) -> None:
        """
        Enqueue an artifact for scanning.

        Args:
            project_id: Project ID
            artifact_id: Artifact ID
        """
        if not self.redis:
            return

        scan_request = {
            "project_id": str(project_id),
            "artifact_id": str(artifact_id),
        }

        await self.redis.rpush(settings.scan_queue_name, json.dumps(scan_request))
        logger.info(f"Enqueued artifact {artifact_id} for virus scan")

    async def process_queue(self) -> int:
        """
        Process one item from the scan queue.

        Returns:
            Number of items processed (0 or 1)
        """
        if not self.redis:
            return 0

        # Pop from queue (blocking, timeout=1 second)
        result = await self.redis.blpop(settings.scan_queue_name, timeout=1)

        if not result:
            return 0

        _, scan_request_json = result
        scan_request = json.loads(scan_request_json)

        project_id = UUID(scan_request["project_id"])
        artifact_id = UUID(scan_request["artifact_id"])

        try:
            # Mock scan: sleep 1 second
            await asyncio.sleep(1)

            # Get artifact
            stmt = select(ArtifactRecord).where(
                ArtifactRecord.artifact_id == artifact_id,
                ArtifactRecord.project_id == project_id,
            )
            result = await self.db.execute(stmt)
            artifact = result.scalar_one_or_none()

            if not artifact:
                logger.warning(f"Artifact {artifact_id} not found for scanning")
                return 1

            # Mark as CLEAN (mock scanner always passes)
            artifact.scan_status = ScanStatus.CLEAN
            artifact.status = ArtifactStatus.AVAILABLE
            artifact.updated_at = asyncio.get_event_loop().time()

            await self.db.flush()
            logger.info(f"Scan completed for artifact {artifact_id}: CLEAN")

            return 1

        except Exception as e:
            logger.error(f"Scan failed for artifact {artifact_id}: {e}")
            # Update scan status to error
            try:
                stmt = select(ArtifactRecord).where(
                    ArtifactRecord.artifact_id == artifact_id,
                    ArtifactRecord.project_id == project_id,
                )
                result = await self.db.execute(stmt)
                artifact = result.scalar_one_or_none()
                if artifact:
                    artifact.scan_status = ScanStatus.SCAN_ERROR
                    await self.db.flush()
            except Exception:
                pass
            return 1

    async def run_scanner_loop(self) -> None:
        """
        Run the scanner in a continuous loop.

        Processes items from the queue continuously.
        """
        logger.info("Starting virus scanner loop")
        try:
            while True:
                try:
                    await self.process_queue()
                except asyncio.CancelledError:
                    logger.info("Scanner loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in scanner loop: {e}")
                    await asyncio.sleep(5)
        finally:
            logger.info("Virus scanner loop stopped")


async def get_or_create_scanner(db: AsyncSession) -> VirusScanner:
    """Get or create the virus scanner instance."""
    scanner = VirusScanner(db)
    await scanner.connect()
    return scanner
