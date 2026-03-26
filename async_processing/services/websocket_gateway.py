"""WebSocket Gateway and Connection Registry - real-time updates."""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from uuid import UUID, uuid4

from fastapi import WebSocket
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from async_processing.config import get_settings
from async_processing.models import WebSocketSession
from async_processing.schemas.tasks import WebSocketMessage, JobStatusUpdate

logger = logging.getLogger(__name__)
settings = get_settings()


class ConnectionRegistry:
    """Registry of active WebSocket connections."""

    def __init__(self, db: AsyncSession):
        self.db = db
        # In-memory registry - maps job_id -> set of session IDs
        self.connections: Dict[UUID, Set[UUID]] = {}

    async def register_connection(
        self, job_id: UUID, project_id: UUID, client_id: Optional[str] = None
    ) -> UUID:
        """
        Register a new WebSocket connection.

        Args:
            job_id: Job being monitored
            project_id: Project ID
            client_id: Optional client identifier

        Returns:
            Session ID
        """
        session_id = uuid4()

        # Create session record
        session = WebSocketSession(
            session_id=session_id,
            job_id=job_id,
            project_id=project_id,
            client_id=client_id,
            status="CONNECTED",
        )

        self.db.add(session)
        await self.db.flush()

        # Add to in-memory registry
        if job_id not in self.connections:
            self.connections[job_id] = set()
        self.connections[job_id].add(session_id)

        logger.info(f"Registered connection {session_id} for job {job_id}")
        return session_id

    async def unregister_connection(self, session_id: UUID) -> Optional[UUID]:
        """
        Unregister a WebSocket connection.

        Args:
            session_id: Session ID to remove

        Returns:
            Job ID if removed, None if not found
        """
        # Find the session
        stmt = select(WebSocketSession).where(
            WebSocketSession.session_id == session_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Mark as disconnected
        session.status = "DISCONNECTED"
        session.disconnected_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Remove from in-memory registry
        if session.job_id in self.connections:
            self.connections[session.job_id].discard(session_id)
            if not self.connections[session.job_id]:
                del self.connections[session.job_id]

        logger.info(f"Unregistered connection {session_id}")
        return session.job_id

    async def get_connections_for_job(self, job_id: UUID) -> Set[UUID]:
        """Get all active session IDs for a job."""
        return self.connections.get(job_id, set())

    async def has_connections(self, job_id: UUID) -> bool:
        """Check if a job has active connections."""
        return job_id in self.connections and len(self.connections[job_id]) > 0

    async def heartbeat(self, session_id: UUID) -> bool:
        """Update heartbeat for a session."""
        stmt = select(WebSocketSession).where(
            WebSocketSession.session_id == session_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.last_heartbeat = datetime.now(timezone.utc)
        await self.db.flush()
        return True


class WebSocketGateway:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = ConnectionRegistry(db)
        # In-memory WebSocket connections
        self.active_connections: Dict[UUID, WebSocket] = {}

    async def connect_client(
        self,
        session_id: UUID,
        websocket: WebSocket,
    ):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"Client connected: {session_id}")

    async def disconnect_client(self, session_id: UUID):
        """Disconnect a WebSocket client."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        await self.registry.unregister_connection(session_id)
        logger.info(f"Client disconnected: {session_id}")

    async def broadcast_to_job(
        self, job_id: UUID, message: WebSocketMessage
    ) -> int:
        """
        Broadcast a message to all clients watching a job.

        Args:
            job_id: Job ID
            message: Message to send

        Returns:
            Number of successful sends
        """
        session_ids = await self.registry.get_connections_for_job(job_id)

        if not session_ids:
            logger.debug(f"No active connections for job {job_id}")
            return 0

        sent_count = 0
        failed_sessions = []

        for session_id in session_ids:
            if session_id not in self.active_connections:
                failed_sessions.append(session_id)
                continue

            try:
                websocket = self.active_connections[session_id]
                await websocket.send_json(message.model_dump(mode="json"))
                await self.registry.heartbeat(session_id)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {session_id}: {e}")
                failed_sessions.append(session_id)

        # Clean up failed sessions
        for session_id in failed_sessions:
            await self.disconnect_client(session_id)

        logger.info(f"Broadcast to job {job_id}: {sent_count} successful")
        return sent_count

    async def send_status_update(
        self, job_id: UUID, status_update: JobStatusUpdate
    ) -> int:
        """Send a job status update to all clients."""
        message = WebSocketMessage(
            message_type="status_update",
            payload=status_update.model_dump(mode="json"),
            timestamp=datetime.now(timezone.utc),
        )

        return await self.broadcast_to_job(job_id, message)

    async def send_heartbeat(self, job_id: UUID) -> int:
        """Send heartbeat message to all clients watching a job."""
        message = WebSocketMessage(
            message_type="heartbeat",
            payload={"job_id": str(job_id)},
            timestamp=datetime.now(timezone.utc),
        )

        return await self.broadcast_to_job(job_id, message)

    async def send_error(
        self, job_id: UUID, error_message: str
    ) -> int:
        """Send error message to all clients."""
        message = WebSocketMessage(
            message_type="error",
            payload={"job_id": str(job_id), "error": error_message},
            timestamp=datetime.now(timezone.utc),
        )

        return await self.broadcast_to_job(job_id, message)

    async def get_active_connection_count(self) -> int:
        """Get total active WebSocket connections."""
        return len(self.active_connections)

    async def get_connections_for_job_count(self, job_id: UUID) -> int:
        """Get active connection count for a job."""
        return len(await self.registry.get_connections_for_job(job_id))
