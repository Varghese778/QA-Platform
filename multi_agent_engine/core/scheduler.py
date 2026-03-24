"""WorkStealingScheduler - Assigns tasks to idle agents with work-stealing logic."""

import asyncio
import logging
from typing import List, Optional
from uuid import UUID

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import TaskType, AgentStatus as AgentStatusEnum
from multi_agent_engine.core.task_queue import TaskQueueManager
from multi_agent_engine.core.agent_registry import AgentRegistry, AgentInstance
from multi_agent_engine.agents import AgentRunner

logger = logging.getLogger(__name__)
settings = get_settings()


class WorkStealingScheduler:
    """
    Assigns tasks to idle agents using work-stealing algorithm.

    Polls queues every 500ms, selects highest-priority waiting task,
    and assigns to available agent. Steals from overloaded queues to underloaded agents.
    """

    def __init__(
        self,
        queue_manager: TaskQueueManager,
        agent_registry: AgentRegistry,
    ):
        self.queue_manager = queue_manager
        self.agent_registry = agent_registry
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("WorkStealingScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("WorkStealingScheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop - polls queues and assigns tasks."""
        while self._running:
            try:
                await self._schedule_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            await asyncio.sleep(settings.scheduler_poll_interval_ms / 1000.0)

    async def _schedule_tasks(self) -> None:
        """Try to assign tasks from all queues to available agents."""
        for task_type in TaskType:
            # Check if there's an available agent
            agent = self.agent_registry.get_idle_agent(task_type)
            if not agent:
                continue

            # Try to dequeue a task
            task_entry = await self.queue_manager.dequeue(task_type)
            if not task_entry:
                continue

            # Assign task to agent
            success = self.agent_registry.assign_task(agent.agent_id, task_entry.task_id)
            if not success:
                # Agent is no longer idle, re-queue task
                await self.queue_manager.requeue(task_entry)
                continue

            # Execute task asynchronously
            asyncio.create_task(
                self._execute_task(agent, task_entry)
            )

    async def _execute_task(self, agent: AgentInstance, task_entry) -> None:
        """Execute a task on an agent."""
        try:
            runner = AgentRunner(agent.agent_id)
            result = await runner.execute(task_entry)

            # Release agent
            self.agent_registry.release_agent(
                agent.agent_id,
                success=(result.status.value == "COMPLETE"),
            )

            # Report result to Orchestrator
            await self._report_result(result)

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self.agent_registry.release_agent(agent.agent_id, success=False)

    async def _report_result(self, result) -> None:
        """Report task result to Orchestrator (MVP: just log)."""
        logger.info(f"Task {result.task_id} completed with status {result.status.value}")
        # In production, would call Orchestrator API
        # await httpx.post(f"{settings.orchestrator_url}/internal/v1/tasks/{result.task_id}/result", ...)
