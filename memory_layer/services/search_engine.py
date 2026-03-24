"""SemanticSearchEngine - Hybrid semantic and metadata search."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.config import get_settings
from memory_layer.models import MemoryRecord, VectorEntry
from memory_layer.schemas import RecordType, TestDomain, SearchResult
from memory_layer.services.embedding_service import EmbeddingService, cosine_similarity

logger = logging.getLogger(__name__)
settings = get_settings()


class SemanticSearchEngine:
    """
    Orchestrates hybrid retrieval: vector similarity + metadata filters.

    Workflow:
    1. Generate embedding for query text
    2. Retrieve vector candidates from VectorStore
    3. Apply metadata filters (tags, domains)
    4. Re-rank by similarity
    5. Return top-k results
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
    ):
        self.db = db
        self.embedding_service = embedding_service

    async def search(
        self,
        project_id: UUID,
        query_text: str,
        top_k: int = 10,
        filter_tags: Optional[List[str]] = None,
        filter_domains: Optional[List[TestDomain]] = None,
        record_type: Optional[RecordType] = None,
    ) -> List[SearchResult]:
        """
        Search for similar records in memory.

        Args:
            project_id: Project to search within.
            query_text: Natural language query.
            top_k: Number of results to return.
            filter_tags: Filter by tags.
            filter_domains: Filter by domains.
            record_type: Filter by record type.

        Returns:
            Ranked list of SearchResult objects.
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.embed_text(query_text)

        # Get candidates from vector store (mock: all records in project)
        candidates = await self._get_vector_candidates(project_id, top_k * settings.agg_multiplier)

        # Apply filters
        filtered = await self._apply_filters(
            candidates,
            record_type=record_type,
            filter_tags=filter_tags,
            filter_domains=filter_domains,
        )

        # Score by similarity
        scored = []
        for record, vector in filtered:
            similarity = cosine_similarity(query_embedding, vector)
            scored.append((record, similarity))

        # Sort by similarity (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        # Truncate to top_k
        top_results = scored[:top_k]

        # Build response
        results = []
        for record, score in top_results:
            from memory_layer.schemas import MemoryRecord as MemoryRecordSchema

            record_schema = MemoryRecordSchema(
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

            results.append(SearchResult(record=record_schema, score=score))

        logger.info(
            f"Search in project {project_id}: returned {len(results)} results "
            f"from {len(scored)} candidates"
        )

        return results

    async def _get_vector_candidates(
        self,
        project_id: UUID,
        limit: int,
    ) -> List[tuple]:
        """
        Get vector candidates for a project.

        Mock: Returns all non-archived records for the project.
        In production: would use ANN index for efficiency.
        """
        stmt = (
            select(MemoryRecord, VectorEntry)
            .join(VectorEntry, MemoryRecord.embedding_id == VectorEntry.embedding_id)
            .where(
                MemoryRecord.project_id == project_id,
                MemoryRecord.archived == False,
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        results = result.all()

        return [(record, vector.vector) for record, vector in results]

    async def _apply_filters(
        self,
        candidates: List[tuple],
        record_type: Optional[RecordType] = None,
        filter_tags: Optional[List[str]] = None,
        filter_domains: Optional[List[TestDomain]] = None,
    ) -> List[tuple]:
        """Apply metadata filters to candidates."""
        filtered = []

        for record, vector in candidates:
            # Filter by record type
            if record_type and record.record_type != record_type:
                continue

            # Filter by tags
            if filter_tags:
                if not any(tag in (record.tags or []) for tag in filter_tags):
                    continue

            # Filter by domains
            if filter_domains:
                domain_strs = [d.value if isinstance(d, TestDomain) else d for d in filter_domains]
                if not any(d in (record.domains or []) for d in domain_strs):
                    continue

            filtered.append((record, vector))

        return filtered
