"""API routes for Async Processing."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from async_processing.config import get_settings
from async_processing.database import get_db
from async_processing.models import EventRecord, WebSocketSession, DeadLetterEntry
from async_processing.schemas.enums import EventType
from async_processing.schemas.tasks import (
    EventRequest,
    EventBatchRequest,
    EventResponse,
    EventRecord as EventRecordSchema,
    EventHistoryResponse,
    HealthResponse,
    DeadLetterEntry as DeadLetterEntrySchema,
    ReplayRequest,
)
from async_processing.services.event_ingestion import EventIngestionAPI
from async_processing.services.websocket_gateway import WebSocketGateway
from async_processing.services.dead_letter_handler import DeadLetterHandler, ReplayEngine

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/v1", tags=["async-processing"])


# =====================================================================
# Event Ingestion Endpoints
# =====================================================================


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    request: EventRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single event."""
    try:
        handler = EventIngestionAPI(db)
        await handler.connect()

        event_id = await handler.ingest_event(
            project_id=request.project_id,
            event_type=request.event_type,
            source_service=request.source_service,
            data=request.data,
            job_id=request.job_id,
            priority=request.priority,
            context=request.context,
        )

        await handler.disconnect()
        await db.commit()

        return EventResponse(
            event_id=event_id,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Failed to ingest event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest event",
        )


@router.post("/events/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(
    request: EventBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple events."""
    try:
        handler = EventIngestionAPI(db)
        await handler.connect()

        event_ids = await handler.ingest_batch(
            [e.model_dump() for e in request.events]
        )

        await handler.disconnect()
        await db.commit()

        return {
            "event_ids": [str(eid) for eid in event_ids],
            "count": len(event_ids),
            "created_at": datetime.now(timezone.utc),
        }

    except Exception as e:
        logger.error(f"Failed to ingest batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest batch",
        )


# =====================================================================
# Event History Endpoints
# =====================================================================


@router.get("/events/{job_id}", response_model=EventHistoryResponse)
async def get_job_events(
    job_id: UUID,
    project_id: UUID = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get event history for a job."""
    try:
        handler = EventIngestionAPI(db)
        events = await handler.get_job_events(
            project_id, job_id, limit, offset
        )

        # Get total count
        from sqlalchemy import and_

        stmt = select(func.count()).select_from(EventRecord).where(
            and_(
                EventRecord.project_id == project_id,
                EventRecord.job_id == job_id,
            )
        )
        result = await db.execute(stmt)
        total_count = result.scalar()

        event_schemas = [
            EventRecordSchema(
                event_id=e.event_id,
                project_id=e.project_id,
                job_id=e.job_id,
                event_type=e.event_type,
                source_service=e.source_service,
                status=e.status,
                priority=e.priority,
                data=e.data,
                context=e.context,
                created_at=e.created_at,
                delivered_at=e.delivered_at,
                failed_at=e.failed_at,
                error_message=e.error_message,
                retry_count=e.retry_count,
                version=e.version,
            )
            for e in events
        ]

        return EventHistoryResponse(
            job_id=job_id,
            events=event_schemas,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Failed to get event history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get event history",
        )


# =====================================================================
# WebSocket Endpoint
# =====================================================================

# Global gateway instance (would be in app state in production)
_gateway: Optional[WebSocketGateway] = None


@router.websocket("/ws/v1/jobs/{job_id}/status")
async def websocket_job_status(
    websocket: WebSocket,
    job_id: UUID,
    project_id: UUID = Query(...),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """WebSocket endpoint for real-time job status updates."""
    if not _gateway:
        await websocket.close(code=status.WS_1011_SERVER_ERROR)
        return

    # Register connection
    registry = _gateway.registry
    session_id = await registry.register_connection(job_id, project_id, client_id)

    try:
        # Accept connection
        await _gateway.connect_client(session_id, websocket)

        # Send initial connection message
        from async_processing.schemas.tasks import WebSocketMessage

        welcome = WebSocketMessage(
            message_type="connected",
            payload={"session_id": str(session_id), "job_id": str(job_id)},
        )
        await websocket.send_json(welcome.model_dump(mode="json"))

        # Keep connection alive
        while True:
            try:
                # Receive messages (for heartbeat keep-alive)
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=settings.websocket_timeout_seconds,
                )

                # Handle incoming messages (e.g., ping)
                if data.get("type") == "ping":
                    pong = {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    await websocket.send_json(pong)

            except asyncio.TimeoutError:
                # Send heartbeat
                await _gateway.send_heartbeat(job_id)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        await _gateway.disconnect_client(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await _gateway.disconnect_client(session_id)
        await websocket.close(code=status.WS_1011_SERVER_ERROR)


# =====================================================================
# Dead Letter Queue Endpoints
# =====================================================================


@router.get("/dead-letter", status_code=status.HTTP_200_OK)
async def list_dead_letter_entries(
    project_id: UUID = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List dead letter queue entries."""
    try:
        handler = DeadLetterHandler(db)
        entries = await handler.get_dlq_entries(project_id, limit, offset)

        return {
            "entries": [
                {
                    "dlq_id": str(e.dlq_id),
                    "original_event_id": str(e.original_event_id),
                    "event_type": e.event_type.value,
                    "reason": e.reason,
                    "retry_count": e.retry_count,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
            ],
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Failed to list DLQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list DLQ",
        )


@router.post("/dead-letter/replay", status_code=status.HTTP_202_ACCEPTED)
async def replay_dead_letter_events(
    request: ReplayRequest,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Replay events from dead letter queue."""
    try:
        engine = ReplayEngine(db)
        new_event_ids = await engine.replay_batch(request.dlq_ids, project_id)

        await db.commit()

        return {
            "new_event_ids": [str(eid) for eid in new_event_ids],
            "count": len(new_event_ids),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to replay: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to replay events",
        )


# =====================================================================
# Health Check
# =====================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        from async_processing import __version__

        # Count active WebSocket connections
        active_connections = 0
        if _gateway:
            active_connections = await _gateway.get_active_connection_count()

        # Count pending events
        stmt = select(func.count()).select_from(EventRecord).where(
            EventRecord.status.in_(["PENDING", "PROCESSING"])
        )
        result = await db.execute(stmt)
        pending_events = result.scalar()

        # Count DLQ entries
        stmt = select(func.count()).select_from(DeadLetterEntry)
        result = await db.execute(stmt)
        dlq_count = result.scalar()

        return HealthResponse(
            status="ok",
            version=__version__,
            active_connections=active_connections,
            pending_events=pending_events,
            dead_letter_count=dlq_count,
            database_latency_ms=0,
            redis_latency_ms=0,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )


# Function to set gateway in routes module
def set_gateway(gateway: WebSocketGateway):
    """Set the WebSocket gateway for routes."""
    global _gateway
    _gateway = gateway
