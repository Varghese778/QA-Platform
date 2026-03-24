"""Knowledge Graph Store - Entity and Relationship management."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_layer.models.memory_record import Entity, Relationship
from memory_layer.schemas.enums import EntityType
from memory_layer.schemas.tasks import (
    Entity as EntitySchema,
    Relationship as RelationshipSchema,
    GraphQueryResponse,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphStore:
    """Manages entity and relationship queries for the knowledge graph."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entity(
        self,
        project_id: UUID,
        entity_type: EntityType,
        entity_name: str,
        attributes: dict,
    ) -> EntitySchema:
        """Create an entity in the knowledge graph."""
        entity = Entity(
            project_id=project_id,
            entity_type=entity_type,
            entity_name=entity_name,
            attributes=attributes,
        )
        self.db.add(entity)
        await self.db.flush()

        logger.info(f"Created entity {entity.entity_id} in project {project_id}")

        return EntitySchema(
            entity_id=entity.entity_id,
            project_id=entity.project_id,
            entity_type=entity.entity_type,
            entity_name=entity.entity_name,
            attributes=entity.attributes,
        )

    async def create_relationship(
        self,
        project_id: UUID,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relationship_type: str,
        metadata: Optional[dict] = None,
    ) -> RelationshipSchema:
        """Create a relationship between entities."""
        relationship = Relationship(
            project_id=project_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relationship_type=relationship_type,
            metadata=metadata or {},
        )
        self.db.add(relationship)
        await self.db.flush()

        logger.info(
            f"Created relationship {relationship.relationship_id} "
            f"from {from_entity_id} to {to_entity_id}"
        )

        return RelationshipSchema(
            relationship_id=relationship.relationship_id,
            from_entity_id=relationship.from_entity_id,
            to_entity_id=relationship.to_entity_id,
            relationship_type=relationship.relationship_type,
            metadata=relationship.metadata,
        )

    async def query_graph(
        self,
        project_id: UUID,
        entity_type: Optional[EntityType] = None,
        entity_name: Optional[str] = None,
        relationship_depth: int = 1,
    ) -> GraphQueryResponse:
        """Query the knowledge graph with optional filtering."""
        # Get entities matching criteria
        entity_stmt = select(Entity).where(Entity.project_id == project_id)

        if entity_type:
            entity_stmt = entity_stmt.where(Entity.entity_type == entity_type)
        if entity_name:
            entity_stmt = entity_stmt.where(Entity.entity_name.icontains(entity_name))

        entity_result = await self.db.execute(entity_stmt)
        entities = entity_result.scalars().all()

        if not entities:
            return GraphQueryResponse(entities=[], relationships=[])

        # Get entity IDs for relationship queries
        entity_ids = [e.entity_id for e in entities]

        # Get relationships involving these entities
        rel_stmt = select(Relationship).where(
            (
                Relationship.from_entity_id.in_(entity_ids)
                | Relationship.to_entity_id.in_(entity_ids)
            )
            & (Relationship.project_id == project_id)
        )

        rel_result = await self.db.execute(rel_stmt)
        relationships = rel_result.scalars().all()

        # Format response
        entity_schemas = [
            EntitySchema(
                entity_id=e.entity_id,
                project_id=e.project_id,
                entity_type=e.entity_type,
                entity_name=e.entity_name,
                attributes=e.attributes,
            )
            for e in entities
        ]

        relationship_schemas = [
            RelationshipSchema(
                relationship_id=r.relationship_id,
                from_entity_id=r.from_entity_id,
                to_entity_id=r.to_entity_id,
                relationship_type=r.relationship_type,
                metadata=r.metadata,
            )
            for r in relationships
        ]

        logger.info(
            f"Graph query project {project_id}: returned {len(entity_schemas)} entities "
            f"and {len(relationship_schemas)} relationships"
        )

        return GraphQueryResponse(
            entities=entity_schemas, relationships=relationship_schemas
        )

    async def get_entity(self, project_id: UUID, entity_id: UUID) -> Optional[Entity]:
        """Get a single entity."""
        stmt = select(Entity).where(
            Entity.project_id == project_id, Entity.entity_id == entity_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_entities(
        self,
        project_id: UUID,
        entity_type: Optional[EntityType] = None,
        limit: int = 100,
    ) -> List[Entity]:
        """List entities in a project."""
        stmt = select(Entity).where(Entity.project_id == project_id)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
