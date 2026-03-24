"""ResultAggregator - Collects and merges task outputs into job result."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from orchestrator_service.models import Task, TaskGraph, TaskStatus, TaskType

logger = logging.getLogger(__name__)


class ResultAggregator:
    """
    Collects per-task outputs and merges into consolidated job result.

    Extracts relevant data from each task type and combines them
    into a final result structure.
    """

    def aggregate_results(self, task_graph: TaskGraph) -> Dict[str, Any]:
        """
        Aggregate results from all completed tasks.

        Args:
            task_graph: The completed task graph.

        Returns:
            Consolidated job result.
        """
        result = {
            "task_graph_id": str(task_graph.task_graph_id),
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_skipped": 0,
            "stages": [],
            "parsed_story": None,
            "domain_classification": None,
            "context_files": [],
            "generated_tests": [],
            "validation_results": None,
            "execution_results": None,
        }

        for task in task_graph.tasks:
            stage_info = {
                "task_id": str(task.task_id),
                "task_type": task.task_type.value,
                "status": task.status.value,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

            if task.status == TaskStatus.COMPLETE:
                result["tasks_completed"] += 1
                self._extract_task_output(result, task)
            elif task.status == TaskStatus.FAILED:
                result["tasks_failed"] += 1
                stage_info["error"] = task.error_message
            elif task.status == TaskStatus.SKIPPED:
                result["tasks_skipped"] += 1

            result["stages"].append(stage_info)

        return result

    def _extract_task_output(self, result: Dict[str, Any], task: Task) -> None:
        """Extract task-specific output into the result."""
        output = task.output_payload or {}

        if task.task_type == TaskType.PARSE_STORY:
            result["parsed_story"] = {
                "title": output.get("title"),
                "actors": output.get("actors", []),
                "actions": output.get("actions", []),
                "preconditions": output.get("preconditions", []),
                "postconditions": output.get("postconditions", []),
                "acceptance_criteria": output.get("acceptance_criteria", []),
            }

        elif task.task_type == TaskType.CLASSIFY_DOMAIN:
            result["domain_classification"] = {
                "domain": output.get("domain"),
                "subdomain": output.get("subdomain"),
                "complexity": output.get("complexity"),
                "suggested_test_types": output.get("suggested_test_types", []),
            }

        elif task.task_type == TaskType.FETCH_CONTEXT:
            result["context_files"] = output.get("files", [])

        elif task.task_type == TaskType.GENERATE_TESTS:
            result["generated_tests"] = output.get("test_cases", [])
            result["test_suite_id"] = output.get("test_suite_id")

        elif task.task_type == TaskType.VALIDATE_TESTS:
            result["validation_results"] = {
                "valid_count": output.get("valid_count", 0),
                "invalid_count": output.get("invalid_count", 0),
                "warnings": output.get("warnings", []),
            }

        elif task.task_type == TaskType.EXECUTE_TESTS:
            result["execution_results"] = {
                "total": output.get("total", 0),
                "passed": output.get("passed", 0),
                "failed": output.get("failed", 0),
                "skipped": output.get("skipped", 0),
                "duration_seconds": output.get("duration_seconds", 0),
                "report_url": output.get("report_url"),
            }

    def get_summary(self, task_graph: TaskGraph) -> Dict[str, Any]:
        """
        Get a brief summary of the task graph status.

        Returns a lightweight status without full output payloads.
        """
        status_counts = {
            "pending": 0,
            "queued": 0,
            "running": 0,
            "complete": 0,
            "failed": 0,
            "skipped": 0,
            "cancelled": 0,
        }

        for task in task_graph.tasks:
            status_key = task.status.value.lower()
            if status_key in status_counts:
                status_counts[status_key] += 1

        total = len(task_graph.tasks)
        completed = status_counts["complete"]
        progress = (completed / total * 100) if total > 0 else 0

        return {
            "task_graph_id": str(task_graph.task_graph_id),
            "total_tasks": total,
            "status_counts": status_counts,
            "progress_percent": round(progress, 1),
            "is_complete": all(t.is_terminal() for t in task_graph.tasks),
        }
