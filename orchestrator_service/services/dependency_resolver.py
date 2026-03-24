"""DependencyResolver - Monitors task completions and unlocks downstream tasks."""

import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.models import (
    Job,
    Task,
    TaskGraph,
    Edge,
    TaskStatus,
    TaskType,
    EdgeCondition,
)
from orchestrator_service.services.state_manager import StateManager

logger = logging.getLogger(__name__)


class DependencyResolver:
    """
    Monitors task completions and unlocks downstream tasks.

    Checks if all prerequisite tasks are satisfied before
    marking dependent tasks as ready for scheduling.
    """

    def __init__(self, db: AsyncSession, state_manager: StateManager):
        self.db = db
        self.state_manager = state_manager

    async def get_task_graph(self, task_graph_id: UUID) -> Optional[TaskGraph]:
        """Get a task graph by ID."""
        stmt = select(TaskGraph).where(TaskGraph.task_graph_id == task_graph_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_dependencies(
        self,
        task_graph: TaskGraph,
        completed_task: Task,
    ) -> List[Task]:
        """
        Check dependencies after a task completes.

        Returns a list of tasks that are now ready to be scheduled.

        Args:
            task_graph: The task graph containing the completed task.
            completed_task: The task that just completed.

        Returns:
            List of tasks that are now unblocked and ready for scheduling.
        """
        unblocked_tasks = []

        # Get downstream edges from the completed task
        downstream_edges = [
            e for e in task_graph.edges if e.from_task_id == completed_task.task_id
        ]

        for edge in downstream_edges:
            # Find the downstream task
            downstream_task = next(
                (t for t in task_graph.tasks if t.task_id == edge.to_task_id),
                None,
            )

            if not downstream_task:
                continue

            # Skip if already processed
            if downstream_task.status != TaskStatus.PENDING:
                continue

            # Check if all upstream dependencies are satisfied
            is_ready, should_skip = await self._check_dependencies(
                task_graph, downstream_task
            )

            if should_skip:
                # Upstream failed with ON_SUCCESS condition
                await self.state_manager.set_task_skipped(downstream_task)
                logger.info(
                    f"Task {downstream_task.task_id} ({downstream_task.task_type.value}) "
                    f"SKIPPED due to upstream failure"
                )
            elif is_ready:
                unblocked_tasks.append(downstream_task)
                logger.info(
                    f"Task {downstream_task.task_id} ({downstream_task.task_type.value}) "
                    f"is now ready for scheduling"
                )

        return unblocked_tasks

    async def _check_dependencies(
        self,
        task_graph: TaskGraph,
        task: Task,
    ) -> Tuple[bool, bool]:
        """
        Check if all dependencies for a task are satisfied.

        Returns:
            Tuple of (is_ready, should_skip).
            - is_ready: True if all dependencies are satisfied
            - should_skip: True if the task should be skipped due to failed dependencies
        """
        # Get all incoming edges
        incoming_edges = [e for e in task_graph.edges if e.to_task_id == task.task_id]

        if not incoming_edges:
            # No dependencies - task is ready
            return True, False

        for edge in incoming_edges:
            # Find the upstream task
            upstream_task = next(
                (t for t in task_graph.tasks if t.task_id == edge.from_task_id),
                None,
            )

            if not upstream_task:
                continue

            if edge.condition == EdgeCondition.ON_SUCCESS:
                # Requires upstream to be COMPLETE
                if upstream_task.status == TaskStatus.FAILED:
                    # Skip this task
                    return False, True
                if upstream_task.status != TaskStatus.COMPLETE:
                    # Not ready yet
                    return False, False
            elif edge.condition == EdgeCondition.ON_ANY:
                # Proceeds on any terminal state
                if not upstream_task.is_terminal():
                    # Not ready yet
                    return False, False

        # All dependencies satisfied
        return True, False

    async def get_ready_tasks(self, task_graph: TaskGraph) -> List[Task]:
        """
        Get all tasks that are ready to be scheduled.

        A task is ready if:
        - It is in PENDING status
        - All its upstream dependencies are satisfied
        """
        ready_tasks = []

        for task in task_graph.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            is_ready, should_skip = await self._check_dependencies(task_graph, task)

            if should_skip:
                await self.state_manager.set_task_skipped(task)
            elif is_ready:
                ready_tasks.append(task)

        return ready_tasks

    def are_generation_tasks_complete(self, task_graph: TaskGraph) -> bool:
        """
        Check if all test generation tasks are complete.

        Generation tasks: PARSE_STORY, CLASSIFY_DOMAIN, FETCH_CONTEXT,
                         GENERATE_TESTS, VALIDATE_TESTS
        """
        generation_types = {
            TaskType.PARSE_STORY,
            TaskType.CLASSIFY_DOMAIN,
            TaskType.FETCH_CONTEXT,
            TaskType.GENERATE_TESTS,
            TaskType.VALIDATE_TESTS,
        }

        for task in task_graph.tasks:
            if task.task_type in generation_types:
                if task.status != TaskStatus.COMPLETE:
                    return False

        return True

    def is_graph_complete(self, task_graph: TaskGraph) -> bool:
        """Check if all tasks in the graph are in terminal state."""
        return all(task.is_terminal() for task in task_graph.tasks)

    def has_critical_failure(self, task_graph: TaskGraph) -> Tuple[bool, Optional[str]]:
        """
        Check if any task has failed after max retries.

        Returns:
            Tuple of (has_failure, error_reason).
        """
        for task in task_graph.tasks:
            if task.status == TaskStatus.FAILED and not task.can_retry():
                return True, f"Task {task.task_type.value} failed: {task.error_message}"

        return False, None

    async def propagate_cancellation(self, task_graph: TaskGraph) -> List[Task]:
        """
        Propagate cancellation to all pending/queued tasks.

        Returns list of cancelled tasks.
        """
        cancelled = []

        for task in task_graph.tasks:
            if task.status in {TaskStatus.PENDING, TaskStatus.QUEUED}:
                await self.state_manager.set_task_cancelled(task)
                cancelled.append(task)

        return cancelled
