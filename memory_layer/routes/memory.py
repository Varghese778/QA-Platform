"""API routes for Memory Layer."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.config import get_settings
from memory_layer.database import get_db
from memory_layer.models import MemoryRecord
from memory_layer.schemas.enums import RecordType, EntityType
from memory_layer.schemas.tasks import (
    SearchRequest,
    SearchResponse,
    WriteRequest,
    WriteResponse,
    UpdateResponse,
    DeleteResponse,
    MemoryRecord as MemoryRecordSchema,
    ConstraintRecord,
    GraphQueryRequest,
    GraphQueryResponse,
    Entity as EntitySchema,
    Relationship as RelationshipSchema,
    HealthResponse,
    ErrorDetail,
)
from memory_layer.services.access_enforcer import AccessEnforcer
from memory_layer.services.search_engine import SemanticSearchEngine
from memory_layer.services.write_handler import WriteHandler
from memory_layer.services.embedding_service import EmbeddingService
from memory_layer.services.knowledge_graph_store import KnowledgeGraphStore

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/v1", tags=["memory"])


# =====================================================================
# Search Endpoints
# =====================================================================


@router.post("/search", response_model=SearchResponse)
async def search_records(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for records using semantic similarity.

    Uses hybrid search combining vector similarity with metadata filters.
    """
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(request.project_id)

        # Initialize services
        embedding_service = EmbeddingService(db)
        search_engine = SemanticSearchEngine(db, embedding_service)

        # Execute search
        results = await search_engine.search(
            project_id=request.project_id,
            query_text=request.query_text,
            top_k=request.top_k,
            filter_tags=request.filter_tags,
            filter_domains=request.filter_domains,
            record_type=request.record_type,
        )

        return SearchResponse(results=results, total_matched=len(results))

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search operation failed",
        )


# =====================================================================
# Record CRUD Endpoints
# =====================================================================


@router.post("/records", response_model=WriteResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    request: WriteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new memory record."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(request.project_id)

        # Write record
        write_handler = WriteHandler(db)
        record_id = await write_handler.write(
            project_id=request.project_id,
            record_type=request.record_type,
            payload=request.record_payload,
            tags=request.tags,
            domains=request.domains,
            source_job_id=request.source_job_id,
            expires_at=request.expires_at,
        )

        return WriteResponse(
            record_id=record_id,
            created_at=datetime.now(timezone.utc),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create record",
        )


@router.get("/records/{record_id}", response_model=MemoryRecordSchema)
async def get_record(
    record_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific record."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Get record
        from sqlalchemy import select

        stmt = select(MemoryRecord).where(
            MemoryRecord.record_id == record_id,
            MemoryRecord.project_id == project_id,
            MemoryRecord.archived == False,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record {record_id} not found",
            )

        return MemoryRecordSchema(
            record_id=record.record_id,
            project_id=record.project_id,
            record_type=record.record_type,
            payload=record.payload,
            tags=record.tags,
            domains=record.domains,
            embedding_id=record.embedding_id,
            source_job_id=record.source_job_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
            version=record.version,
        )

    except Exception as e:
        logger.error(f"Failed to get record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get record",
        )


@router.put("/records/{record_id}", response_model=UpdateResponse)
async def update_record(
    record_id: UUID,
    request: WriteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing record."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(request.project_id)

        # Get existing record
        from sqlalchemy import select

        stmt = select(MemoryRecord).where(
            MemoryRecord.record_id == record_id,
            MemoryRecord.project_id == request.project_id,
            MemoryRecord.archived == False,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record {record_id} not found",
            )

        # Update record
        record.payload = request.record_payload
        record.tags = request.tags or record.tags
        record.domains = request.domains or record.domains
        record.expires_at = request.expires_at or record.expires_at
        record.version += 1
        record.updated_at = datetime.now(timezone.utc)

        await db.flush()

        return UpdateResponse(
            record_id=record.record_id,
            updated_at=record.updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to update record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update record",
        )


@router.delete("/records/{record_id}", response_model=DeleteResponse)
async def delete_record(
    record_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete a record (soft delete)."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Get record
        from sqlalchemy import select

        stmt = select(MemoryRecord).where(
            MemoryRecord.record_id == record_id,
            MemoryRecord.project_id == project_id,
            MemoryRecord.archived == False,
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record {record_id} not found",
            )

        # Soft delete
        record.archived = True
        record.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return DeleteResponse(deleted=True)

    except Exception as e:
        logger.error(f"Failed to delete record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete record",
        )


@router.get("/records", response_model=SearchResponse)
async def list_records(
    project_id: UUID = Query(...),
    record_type: RecordType = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List records in a project with optional filtering."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Build query
        from sqlalchemy import select

        stmt = select(MemoryRecord).where(
            MemoryRecord.project_id == project_id,
            MemoryRecord.archived == False,
        )

        if record_type:
            stmt = stmt.where(MemoryRecord.record_type == record_type)

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        records = result.scalars().all()

        # Convert to response
        from memory_layer.schemas.tasks import SearchResult

        results = [
            SearchResult(
                record=MemoryRecordSchema(
                    record_id=r.record_id,
                    project_id=r.project_id,
                    record_type=r.record_type,
                    payload=r.payload,
                    tags=r.tags,
                    domains=r.domains,
                    embedding_id=r.embedding_id,
                    source_job_id=r.source_job_id,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    expires_at=r.expires_at,
                    version=r.version,
                ),
                score=1.0,
            )
            for r in records
        ]

        return SearchResponse(results=results, total_matched=len(results))

    except Exception as e:
        logger.error(f"Failed to list records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list records",
        )


# =====================================================================
# Constraint Endpoints
# =====================================================================


@router.get("/constraints", response_model=list[ConstraintRecord])
async def list_constraints(
    project_id: UUID = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all constraints in a project."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Get constraint records
        from sqlalchemy import select

        stmt = select(MemoryRecord).where(
            MemoryRecord.project_id == project_id,
            MemoryRecord.record_type == RecordType.CONSTRAINT,
            MemoryRecord.archived == False,
        )

        result = await db.execute(stmt)
        records = result.scalars().all()

        # Convert to constraint format
        constraints = [
            ConstraintRecord(
                record_id=r.record_id,
                constraint_name=r.payload.get("constraint_name"),
                rule=r.payload.get("rule"),
                scope=r.payload.get("scope"),
                applies_to=r.payload.get("applies_to"),
                priority=r.payload.get("priority"),
            )
            for r in records
        ]

        return constraints[:limit]

    except Exception as e:
        logger.error(f"Failed to list constraints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list constraints",
        )


# =====================================================================
# Knowledge Graph Endpoints
# =====================================================================


@router.post("/graph/query", response_model=GraphQueryResponse)
async def query_graph(
    request: GraphQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Query the knowledge graph."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(request.project_id)

        # Query graph
        graph_store = KnowledgeGraphStore(db)
        response = await graph_store.query_graph(
            project_id=request.project_id,
            entity_type=request.entity_type,
            entity_name=request.entity_name,
            relationship_depth=request.relationship_depth,
        )

        return response

    except Exception as e:
        logger.error(f"Failed to query graph: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query graph",
        )


@router.post("/entities", response_model=EntitySchema, status_code=status.HTTP_201_CREATED)
async def create_entity(
    project_id: UUID = Query(...),
    entity_type: EntityType = Query(...),
    entity_name: str = Query(...),
    attributes: dict = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Create an entity in the knowledge graph."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Create entity
        graph_store = KnowledgeGraphStore(db)
        entity = await graph_store.create_entity(
            project_id=project_id,
            entity_type=entity_type,
            entity_name=entity_name,
            attributes=attributes or {},
        )

        await db.commit()
        return entity

    except Exception as e:
        logger.error(f"Failed to create entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create entity",
        )


@router.post("/relationships", response_model=RelationshipSchema, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    project_id: UUID = Query(...),
    from_entity_id: UUID = Query(...),
    to_entity_id: UUID = Query(...),
    relationship_type: str = Query(...),
    metadata: dict = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Create a relationship in the knowledge graph."""
    try:
        # Enforce access control
        enforcer = AccessEnforcer()
        await enforcer.check_project_access(project_id)

        # Create relationship
        graph_store = KnowledgeGraphStore(db)
        relationship = await graph_store.create_relationship(
            project_id=project_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relationship_type=relationship_type,
            metadata=metadata or {},
        )

        await db.commit()
        return relationship

    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create relationship",
        )


# =====================================================================
# Health Check
# =====================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        from memory_layer import __version__

        # Count records
        from sqlalchemy import select, func

        stmt = select(func.count()).select_from(MemoryRecord)
        result = await db.execute(stmt)
        record_count = result.scalar()

        return HealthResponse(
            status="ok",
            version=__version__,
            vector_store_latency_ms=0,
            record_count=record_count or 0,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )
