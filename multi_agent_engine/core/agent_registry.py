"""AgentRegistry - Maintains live agent instance registry."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import redis.asyncio as redis

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import (
    TaskType,
    AgentStatus,
    AgentStatusResponse,
)
from multi_agent_engine.core.task_queue import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key patterns
AGENT_KEY_PREFIX = "agent:"
AGENTS_BY_TYPE_KEY_PREFIX = "agents_by_type:"


class AgentInstance:
    """Represents a single agent instance."""

    def __init__(
        self,
        agent_id: UUID,
        agent_type: TaskType,
        status: AgentStatus = AgentStatus.IDLE,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.status = status
        self.current_task_id: Optional[UUID] = None
        self.tasks_completed: int = 0
        self.tasks_failed: int = 0
        self.last_heartbeat: datetime = datetime.now(timezone.utc)

    def to_response(self) -> AgentStatusResponse:
        """Convert to API response model."""
        return AgentStatusResponse(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            status=self.status,
            current_task_id=self.current_task_id,
            tasks_completed=self.tasks_completed,
            tasks_failed=self.tasks_failed,
            last_heartbeat=self.last_heartbeat,
        )


class AgentRegistry:
    """
    Maintains live agent instance registry.

    Uses in-memory storage for local instance with Redis for cluster view.
    """

    def __init__(self):
        # Local agent instances (in-memory)
        self._agents: Dict[UUID, AgentInstance] = {}
        # Index by type for quick lookup
        self._agents_by_type: Dict[TaskType, List[UUID]] = {t: [] for t in TaskType}
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the heartbeat background task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("AgentRegistry started")

    async def stop(self) -> None:
        """Stop the heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        logger.info("AgentRegistry stopped")

    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeats to Redis."""
        while True:
            try:
                await self._send_heartbeats()
                await self._check_offline_agents()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(settings.agent_heartbeat_interval_seconds)

    async def _send_heartbeats(self) -> None:
        """Send heartbeat for all local agents to Redis."""
        redis_client = await get_redis()
        now = datetime.now(timezone.utc)

        for agent in self._agents.values():
            agent.last_heartbeat = now
            # Store in Redis for cluster visibility
            await redis_client.setex(
                f"{AGENT_KEY_PREFIX}{agent.agent_id}",
                settings.agent_offline_threshold_seconds * 2,
                agent.to_response().model_dump_json(),
            )

    async def _check_offline_agents(self) -> None:
        """Mark agents as offline if heartbeat missed."""
        now = datetime.now(timezone.utc)
        threshold = settings.agent_offline_threshold_seconds

        for agent in self._agents.values():
            if agent.status != AgentStatus.OFFLINE:
                elapsed = (now - agent.last_heartbeat).total_seconds()
                if elapsed > threshold:
                    logger.warning(f"Agent {agent.agent_id} marked OFFLINE (no heartbeat)")
                    agent.status = AgentStatus.OFFLINE

    def register_agent(
        self,
        agent_type: TaskType,
        agent_id: Optional[UUID] = None,
    ) -> AgentInstance:
        """
        Register a new agent instance.

        Returns:
            The registered agent instance.
        """
        if agent_id is None:
            agent_id = uuid4()

        agent = AgentInstance(agent_id=agent_id, agent_type=agent_type)
        self._agents[agent_id] = agent
        self._agents_by_type[agent_type].append(agent_id)

        logger.info(f"Registered agent {agent_id} of type {agent_type.value}")
        return agent

    def unregister_agent(self, agent_id: UUID) -> bool:
        """
        Remove an agent from the registry.

        Returns:
            True if agent was removed.
        """
        agent = self._agents.pop(agent_id, None)
        if agent:
            self._agents_by_type[agent.agent_type].remove(agent_id)
            logger.info(f"Unregistered agent {agent_id}")
            return True
        return False

    def get_agent(self, agent_id: UUID) -> Optional[AgentInstance]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_type(self, agent_type: TaskType) -> List[AgentInstance]:
        """Get all agents of a specific type."""
        return [
            self._agents[aid]
            for aid in self._agents_by_type[agent_type]
            if aid in self._agents
        ]

    def get_idle_agent(self, agent_type: TaskType) -> Optional[AgentInstance]:
        """
        Get an idle agent of the specified type.

        Returns:
            An idle agent or None if none available.
        """
        for agent_id in self._agents_by_type[agent_type]:
            agent = self._agents.get(agent_id)
            if agent and agent.status == AgentStatus.IDLE:
                return agent
        return None

    def assign_task(self, agent_id: UUID, task_id: UUID) -> bool:
        """
        Assign a task to an agent.

        Returns:
            True if assignment successful.
        """
        agent = self._agents.get(agent_id)
        if not agent or agent.status != AgentStatus.IDLE:
            return False

        agent.status = AgentStatus.BUSY
        agent.current_task_id = task_id
        logger.debug(f"Assigned task {task_id} to agent {agent_id}")
        return True

    def release_agent(
        self,
        agent_id: UUID,
        success: bool = True,
    ) -> bool:
        """
        Release an agent after task completion.

        Returns:
            True if agent was released.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent.status = AgentStatus.IDLE
        agent.current_task_id = None

        if success:
            agent.tasks_completed += 1
        else:
            agent.tasks_failed += 1

        logger.debug(f"Released agent {agent_id} (success={success})")
        return True

    def set_draining(self, agent_id: UUID) -> bool:
        """Set an agent to draining state (won't accept new tasks)."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent.status = AgentStatus.DRAINING
        return True

    def get_all_agents(self) -> List[AgentInstance]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_agent_count(self, agent_type: Optional[TaskType] = None) -> int:
        """Get count of agents, optionally filtered by type."""
        if agent_type:
            return len(self._agents_by_type[agent_type])
        return len(self._agents)

    def get_idle_count(self, agent_type: Optional[TaskType] = None) -> int:
        """Get count of idle agents."""
        agents = self.get_agents_by_type(agent_type) if agent_type else self.get_all_agents()
        return sum(1 for a in agents if a.status == AgentStatus.IDLE)

    def get_busy_count(self, agent_type: Optional[TaskType] = None) -> int:
        """Get count of busy agents."""
        agents = self.get_agents_by_type(agent_type) if agent_type else self.get_all_agents()
        return sum(1 for a in agents if a.status == AgentStatus.BUSY)

    def has_available_agent(self, agent_type: TaskType) -> bool:
        """Check if there's an available agent of the specified type."""
        return self.get_idle_agent(agent_type) is not None
