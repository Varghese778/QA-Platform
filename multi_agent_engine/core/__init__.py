"""Core package - exports core components."""

from multi_agent_engine.core.task_queue import (
    TaskQueueManager,
    QueueFullError,
    DuplicateTaskError,
    get_redis,
    close_redis,
)
from multi_agent_engine.core.agent_registry import (
    AgentRegistry,
    AgentInstance,
)
from multi_agent_engine.core.scheduler import WorkStealingScheduler
from multi_agent_engine.core.retry_coordinator import RetryCoordinator

__all__ = [
    "TaskQueueManager",
    "QueueFullError",
    "DuplicateTaskError",
    "get_redis",
    "close_redis",
    "AgentRegistry",
    "AgentInstance",
    "WorkStealingScheduler",
    "RetryCoordinator",
]
