"""Consumer Worker - reads from Redis Streams and dispatches events."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from async_processing.config import get_settings
from async_processing.models import EventRecord
from async_processing.schemas.enums import EventStatus, EventType
from async_processing.schemas.tasks import JobStatusUpdate
from async_processing.services.websocket_gateway import WebSocketGateway

logger = logging.getLogger(__name__)
settings = get_settings()


class ConsumerWorker:
    """Processes events from Redis Stream and dispatches to WebSocket clients."""

    def __init__(self, db: AsyncSession, gateway: WebSocketGateway):
        self.db = db
        self.gateway = gateway
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await redis.from_url(settings.redis_url)
        logger.info("ConsumerWorker connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def process_events(self) -> int:
        """
        Process one batch of events from Redis Stream.

        Uses consumer group for reliable delivery.

        Returns:
            Number of events processed
        """
        if not self.redis:
            return 0

        try:
            # Try to create consumer group (will fail if exists, which is fine)
            try:
                await self.redis.xgroup_create(
                    settings.event_stream_name,
                    settings.consumer_group_name,
                    id="0",
                    mkstream=True,
                )
            except redis.ResponseError:
                # Group already exists
                pass

            # Read new messages
            messages = await self.redis.xreadgroup(
                groupname=settings.consumer_group_name,
                consumername=settings.consumer_name,
                streams={settings.event_stream_name: ">"},
                count=settings.stream_read_count,
                block=settings.stream_block_timeout_ms,
            )

            if not messages:
                return 0

            processed = 0

            for stream_name, message_list in messages:
                for message_id, message_data in message_list:
                    try:
                        await self._process_single_event(
                            message_id, message_data
                        )
                        processed += 1

                        # Acknowledge the message
                        await self.redis.xack(
                            settings.event_stream_name,
                            settings.consumer_group_name,
                            message_id,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process message {message_id}: {e}"
                        )

            logger.info(f"Processed {processed} events from stream")
            return processed

        except Exception as e:
            logger.error(f"Error in ProcessEvents: {e}")
            return 0

    async def _process_single_event(
        self, message_id: bytes, message_data: dict
    ):
        """Process a single event message."""
        # Decode message data
        event_id_bytes = message_data.get(b"event_id")
        job_id_bytes = message_data.get(b"job_id")
        event_type_bytes = message_data.get(b"event_type")

        if not event_id_bytes or not event_type_bytes:
            logger.warning(f"Invalid message {message_id}: missing required fields")
            return

        event_id = UUID(event_id_bytes.decode())
        job_id = (
            UUID(job_id_bytes.decode())
            if job_id_bytes and job_id_bytes != b"None"
            else None
        )
        event_type_str = event_type_bytes.decode()

        logger.debug(
            f"Processing event {event_id} type={event_type_str}"
        )

        # Update event status
        stmt = (
            update(EventRecord)
            .where(EventRecord.event_id == event_id)
            .values(
                status=EventStatus.PROCESSING,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

        try:
            # If event has a job_id, broadcast to WebSocket clients
            if job_id:
                await self._broadcast_event(
                    event_id, job_id, event_type_str, message_data
                )

            # Mark as delivered
            stmt = (
                update(EventRecord)
                .where(EventRecord.event_id == event_id)
                .values(
                    status=EventStatus.DELIVERED,
                    delivered_at=datetime.now(timezone.utc),
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()

            logger.info(f"Successfully processed event {event_id}")

        except Exception as e:
            logger.error(f"Error processing event {event_id}: {e}")

            # Mark as failed
            stmt = (
                update(EventRecord)
                .where(EventRecord.event_id == event_id)
                .values(
                    status=EventStatus.FAILED,
                    failed_at=datetime.now(timezone.utc),
                    error_message=str(e)[:500],
                    retry_count=EventRecord.retry_count + 1,
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()

    async def _broadcast_event(
        self, event_id: UUID, job_id: UUID, event_type: str, message_data: dict
    ):
        """Broadcast event to WebSocket clients."""
        # Parse event type
        try:
            evt_type = EventType(event_type)
        except ValueError:
            logger.warning(f"Unknown event type: {event_type}")
            return

        # Create status update based on event type
        if evt_type == EventType.JOB_STARTED:
            update = JobStatusUpdate(
                job_id=job_id,
                status="RUNNING",
                message="Job started",
            )
            await self.gateway.send_status_update(job_id, update)

        elif evt_type == EventType.JOB_COMPLETED:
            update = JobStatusUpdate(
                job_id=job_id,
                status="COMPLETED",
                progress_percent=100,
                message="Job completed",
            )
            await self.gateway.send_status_update(job_id, update)

        elif evt_type == EventType.JOB_FAILED:
            data_bytes = message_data.get(b"data", b"{}")
            try:
                data = json.loads(data_bytes.decode())
                error = data.get("error_message", "Job failed")
            except:
                error = "Job failed"

            update = JobStatusUpdate(
                job_id=job_id,
                status="FAILED",
                message=error,
            )
            await self.gateway.send_status_update(job_id, update)

        elif evt_type == EventType.JOB_PROGRESSED:
            data_bytes = message_data.get(b"data", b"{}")
            try:
                data = json.loads(data_bytes.decode())
                progress = data.get("progress_percent", 0)
            except:
                progress = 0

            update = JobStatusUpdate(
                job_id=job_id,
                status="RUNNING",
                progress_percent=progress,
                message="Job in progress",
            )
            await self.gateway.send_status_update(job_id, update)

    async def run_consumer_loop(self):
        """Run the consumer in a continuous loop."""
        logger.info("Starting consumer worker loop")
        try:
            while True:
                try:
                    await self.process_events()
                except asyncio.CancelledError:
                    logger.info("Consumer loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in consumer loop: {e}")
                    await asyncio.sleep(5)
        finally:
            logger.info("Consumer worker loop stopped")


async def get_or_create_worker(
    db: AsyncSession, gateway: WebSocketGateway
) -> ConsumerWorker:
    """Get or create consumer worker instance."""
    worker = ConsumerWorker(db, gateway)
    await worker.connect()
    return worker
