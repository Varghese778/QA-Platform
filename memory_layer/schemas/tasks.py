"""Pydantic schemas for Memory Layer."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from memory_layer.schemas.enums import (
    RecordType,
    TestResultType,
    ConstraintScope,
    ConstraintPriority,
    EntityType,
    TestDomain,
)


# =====================================================================
# Payload Schemas (for record_payload field)
# =====================================================================


class TestStep(BaseModel):
    """Single step within a test case."""

    step_number: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    input_data: Optional[Dict[str, Any]] = None
    expected_outcome: str = Field(..., min_length=1)


class ExecutionSummary(BaseModel):
    """Summary of test execution history."""

    execution_id: UUID
    executed_at: datetime
    result: TestResultType
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None


class TestCasePayload(BaseModel):
    """Payload for TEST_CASE record type."""

    test_id: UUID
    title: str = Field(..., min_length=1, max_length=200)
    steps: List[TestStep] = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)
    execution_history: List[ExecutionSummary] = Field(default_factory=list)
    last_result: Optional[TestResultType] = None


class PatternPayload(BaseModel):
    """Payload for PATTERN record type."""

    pattern_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    template: str = Field(..., min_length=1)
    applicable_domains: List[str] = Field(default_factory=list)
    usage_count: int = Field(default=0, ge=0)


class ConstraintPayload(BaseModel):
    """Payload for CONSTRAINT record type."""

    constraint_name: str = Field(..., min_length=1, max_length=100)
    rule: str = Field(..., min_length=1, max_length=1000)
    scope: ConstraintScope
    applies_to: Optional[str] = Field(None, description="Domain or actor name")
    priority: ConstraintPriority


class EntityPayload(BaseModel):
    """Payload for ENTITY record type."""

    entity_type: EntityType
    entity_name: str = Field(..., min_length=1, max_length=200)
    attributes: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Request/Response Schemas
# =====================================================================


class SearchRequest(BaseModel):
    """Request schema for semantic search."""

    project_id: UUID
    query_text: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    filter_tags: Optional[List[str]] = Field(default=None, max_length=10)
    filter_domains: Optional[List[TestDomain]] = Field(default=None, max_length=6)
    record_type: Optional[RecordType] = None


class WriteRequest(BaseModel):
    """Request schema for writing records."""

    project_id: UUID
    record_type: RecordType
    record_payload: Dict[str, Any] = Field(
        ..., description="Type-specific payload"
    )
    tags: Optional[List[str]] = Field(default=None, max_length=20)
    domains: Optional[List[TestDomain]] = Field(default=None, max_length=6)
    source_job_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None

    @field_validator("record_payload")
    @classmethod
    def validate_payload_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload size."""
        import json
        serialized = json.dumps(v)
        if len(serialized) > 65536:  # 64 KB
            raise ValueError("Payload exceeds maximum size of 64 KB")
        return v


class MemoryRecord(BaseModel):
    """Full memory record response."""

    record_id: UUID
    project_id: UUID
    record_type: RecordType
    payload: Dict[str, Any]
    tags: Optional[List[str]] = None
    domains: Optional[List[TestDomain]] = None
    embedding_id: Optional[UUID] = None
    source_job_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    version: int


class SearchResult(BaseModel):
    """Individual search result with score."""

    record: MemoryRecord
    score: float = Field(..., ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Response for semantic search."""

    results: List[SearchResult]
    total_matched: int


class WriteResponse(BaseModel):
    """Response for write operations."""

    record_id: UUID
    created_at: datetime


class UpdateResponse(BaseModel):
    """Response for update operations."""

    record_id: UUID
    updated_at: datetime


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    deleted: bool = True


class ConstraintRecord(BaseModel):
    """Constraint record response."""

    record_id: UUID
    constraint_name: str
    rule: str
    scope: ConstraintScope
    applies_to: Optional[str] = None
    priority: ConstraintPriority


class Entity(BaseModel):
    """Entity in knowledge graph."""

    entity_id: UUID
    project_id: UUID
    entity_type: EntityType
    entity_name: str
    attributes: Dict[str, Any]


class Relationship(BaseModel):
    """Relationship in knowledge graph."""

    relationship_id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    relationship_type: str
    metadata: Optional[Dict[str, Any]] = None


class GraphQueryRequest(BaseModel):
    """Request for knowledge graph query."""

    project_id: UUID
    entity_type: Optional[EntityType] = None
    entity_name: Optional[str] = None
    relationship_depth: int = Field(default=1, ge=1, le=3)


class GraphQueryResponse(BaseModel):
    """Response for graph query."""

    entities: List[Entity]
    relationships: List[Relationship]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    vector_store_latency_ms: int = 0
    record_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    """Error detail response."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
