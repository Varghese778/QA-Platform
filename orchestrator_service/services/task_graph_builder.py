"""TaskGraphBuilder - Decomposes user story into ordered task DAG."""

import logging
import uuid
from typing import Dict, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.config import get_settings
from orchestrator_service.models import (
    Job,
    Task,
    TaskGraph,
    Edge,
    TaskType,
    TaskStatus,
    EdgeCondition,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# Default pipeline order
DEFAULT_PIPELINE = [
    TaskType.PARSE_STORY,
    TaskType.CLASSIFY_DOMAIN,
    TaskType.FETCH_CONTEXT,
    TaskType.GENERATE_TESTS,
    TaskType.VALIDATE_TESTS,
    TaskType.EXECUTE_TESTS,
]


class GraphBuildError(Exception):
    """Raised when graph construction fails."""

    def __init__(self, message: str, code: str = "GRAPH_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class TaskGraphBuilder:
    """
    Decomposes a job into a directed acyclic graph of tasks.

    Default pipeline: PARSE_STORY → CLASSIFY_DOMAIN → FETCH_CONTEXT
                      → GENERATE_TESTS → VALIDATE_TESTS → EXECUTE_TESTS
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_graph(self, job: Job) -> TaskGraph:
        """
        Build a TaskGraph for the given job.

        Args:
            job: The job to build a graph for.

        Returns:
            The constructed TaskGraph with all tasks and edges.

        Raises:
            GraphBuildError: If graph construction fails.
        """
        logger.info(f"Building task graph for job {job.job_id}")

        # Create the graph
        task_graph = TaskGraph(
            task_graph_id=uuid.uuid4(),
            job_id=job.job_id,
        )
        self.db.add(task_graph)

        # Create tasks for each pipeline stage
        tasks = await self._create_tasks(task_graph, job)

        if not tasks:
            raise GraphBuildError(
                "No tasks generated from user story",
                code="INVALID_STORY",
            )

        # Create edges between consecutive tasks
        edges = await self._create_edges(task_graph, tasks)

        # Validate no circular dependencies
        if self._has_cycle(tasks, edges):
            raise GraphBuildError(
                "Circular dependency detected in task graph",
                code="GRAPH_ERROR",
            )

        # Update job with graph reference
        job.task_graph_id = task_graph.task_graph_id

        await self.db.flush()

        logger.info(
            f"Built task graph {task_graph.task_graph_id} with "
            f"{len(tasks)} tasks and {len(edges)} edges"
        )

        return task_graph

    async def _create_tasks(
        self,
        task_graph: TaskGraph,
        job: Job,
    ) -> List[Task]:
        """Create task nodes for the pipeline."""
        tasks = []

        for task_type in DEFAULT_PIPELINE:
            task = Task(
                task_id=uuid.uuid4(),
                task_graph_id=task_graph.task_graph_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                input_payload=self._build_input_payload(task_type, job),
                timeout_seconds=settings.task_timeouts.get(
                    task_type.value,
                    settings.default_task_timeout_seconds,
                ),
                max_retries=settings.max_task_retries,
            )
            self.db.add(task)
            tasks.append(task)

        task_graph.tasks = tasks
        return tasks

    async def _create_edges(
        self,
        task_graph: TaskGraph,
        tasks: List[Task],
    ) -> List[Edge]:
        """Create dependency edges between tasks."""
        edges = []

        # Create sequential edges: task[i] -> task[i+1]
        for i in range(len(tasks) - 1):
            edge = Edge(
                from_task_id=tasks[i].task_id,
                to_task_id=tasks[i + 1].task_id,
                task_graph_id=task_graph.task_graph_id,
                condition=EdgeCondition.ON_SUCCESS,
            )
            self.db.add(edge)
            edges.append(edge)

        task_graph.edges = edges
        return edges

    def _build_input_payload(self, task_type: TaskType, job: Job) -> Dict:
        """Build task-specific input payload."""
        base_payload = {
            "job_id": str(job.job_id),
            "project_id": str(job.project_id),
        }

        if task_type == TaskType.PARSE_STORY:
            return {
                **base_payload,
                "story_title": job.story_title,
                "user_story": job.user_story,
            }
        elif task_type == TaskType.CLASSIFY_DOMAIN:
            return {
                **base_payload,
                "user_story": job.user_story,
                "tags": job.tags or [],
            }
        elif task_type == TaskType.FETCH_CONTEXT:
            return {
                **base_payload,
                "file_ids": [str(fid) for fid in (job.file_ids or [])],
            }
        elif task_type == TaskType.GENERATE_TESTS:
            return {
                **base_payload,
                "environment_target": job.environment_target.value,
            }
        elif task_type == TaskType.VALIDATE_TESTS:
            return base_payload
        elif task_type == TaskType.EXECUTE_TESTS:
            return {
                **base_payload,
                "environment_target": job.environment_target.value,
            }
        else:
            return base_payload

    def _has_cycle(self, tasks: List[Task], edges: List[Edge]) -> bool:
        """
        Detect cycles in the task graph using DFS.

        Returns True if a cycle exists.
        """
        # Build adjacency list
        adj: Dict[uuid.UUID, List[uuid.UUID]] = {t.task_id: [] for t in tasks}
        for edge in edges:
            adj[edge.from_task_id].append(edge.to_task_id)

        # Track visited and current path
        visited = set()
        in_path = set()

        def dfs(node: uuid.UUID) -> bool:
            if node in in_path:
                return True  # Cycle detected
            if node in visited:
                return False

            visited.add(node)
            in_path.add(node)

            for neighbor in adj.get(node, []):
                if dfs(neighbor):
                    return True

            in_path.remove(node)
            return False

        for task in tasks:
            if task.task_id not in visited:
                if dfs(task.task_id):
                    return True

        return False

    def get_root_tasks(self, task_graph: TaskGraph) -> List[Task]:
        """
        Get tasks with no incoming dependencies (root nodes).

        These are the first tasks to be scheduled.
        """
        # Get all task IDs that have incoming edges
        has_incoming = {edge.to_task_id for edge in task_graph.edges}

        # Return tasks without incoming edges
        return [t for t in task_graph.tasks if t.task_id not in has_incoming]

    def get_downstream_tasks(
        self,
        task_graph: TaskGraph,
        task_id: uuid.UUID,
    ) -> List[Tuple[Task, EdgeCondition]]:
        """
        Get tasks that depend on the given task.

        Returns list of (task, condition) tuples.
        """
        result = []
        for edge in task_graph.edges:
            if edge.from_task_id == task_id:
                # Find the downstream task
                for task in task_graph.tasks:
                    if task.task_id == edge.to_task_id:
                        result.append((task, edge.condition))
                        break
        return result

    def get_upstream_tasks(
        self,
        task_graph: TaskGraph,
        task_id: uuid.UUID,
    ) -> List[Tuple[Task, EdgeCondition]]:
        """
        Get tasks that the given task depends on.

        Returns list of (task, condition) tuples.
        """
        result = []
        for edge in task_graph.edges:
            if edge.to_task_id == task_id:
                # Find the upstream task
                for task in task_graph.tasks:
                    if task.task_id == edge.from_task_id:
                        result.append((task, edge.condition))
                        break
        return result
