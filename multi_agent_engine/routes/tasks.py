"""API routes for Multi-Agent Engine."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import (
    TaskType,
    TaskCreateRequest,
    TaskAcceptedResponse,
    TaskStatusResponse,
    AgentListResponse,
    QueueDepthResponse,
    HealthResponse,
    ErrorResponse,
)
from multi_agent_engine.core.task_queue import (
    TaskQueueManager,
    QueueFullError,
    DuplicateTaskError,
    get_redis,
)
from multi_agent_engine.core.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/v1", tags=["multi-agent-engine"])

# Global instances (would normally be injected)
_queue_manager: Optional[TaskQueueManager] = None
_agent_registry: Optional[AgentRegistry] = None


async def get_queue_manager() -> TaskQueueManager:
    """Get task queue manager."""
    global _queue_manager
    if _queue_manager is None:
        redis_client = await get_redis()
        _queue_manager = TaskQueueManager(redis_client)
    return _queue_manager


async def get_agent_registry() -> AgentRegistry:
    """Get agent registry."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry


@router.post("/tasks", response_model=TaskAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    request: TaskCreateRequest,
    queue_manager: TaskQueueManager = Depends(get_queue_manager),
):
    """
    Ingest a new task from the Orchestrator.

    Tasks are validated, prioritized, and added to the appropriate queue.
    """
    try:
        # Enqueue the task
        entry = await queue_manager.enqueue(
            task_id=request.task_id,
            task_type=request.task_type,
            job_id=request.job_id,
            project_id=request.project_id,
            payload=request.payload,
            context=request.context,
            priority=request.priority,
            timeout_seconds=request.timeout_seconds,
            retry_attempt=request.retry_attempt,
            model_config=request.model_config_override.model_dump() if request.model_config_override else None,
        )

        return TaskAcceptedResponse(
            task_id=request.task_id,
            queued_at=entry.enqueued_at,
        )

    except DuplicateTaskError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {request.task_id} already exists",
        )
    except QueueFullError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Queue for {e.task_type.value} is full",
        )
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue task",
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    queue_manager: TaskQueueManager = Depends(get_queue_manager),
):
    """Get the status of a specific task."""
    task = await queue_manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        agent_id=None,  # Would be populated from execution state
        queued_at=task.enqueued_at,
        started_at=task.dequeued_at,
        completed_at=None,
    )


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
):
    """Get the status of all agent instances."""
    agents = agent_registry.get_all_agents()

    return AgentListResponse(
        agents=[agent.to_response() for agent in agents]
    )


@router.get("/queue/depth", response_model=QueueDepthResponse)
async def get_queue_depth(
    task_type: TaskType = Query(..., description="Agent type filter"),
    queue_manager: TaskQueueManager = Depends(get_queue_manager),
):
    """Get queue depth for a specific agent type."""
    depth = await queue_manager.get_queue_depth(task_type)
    oldest_at = await queue_manager.get_oldest_queued_at(task_type)

    return QueueDepthResponse(
        task_type=task_type,
        depth=depth,
        oldest_queued_at=oldest_at,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    queue_manager: TaskQueueManager = Depends(get_queue_manager),
):
    """Health check endpoint."""
    from multi_agent_engine import __version__

    # Count online agents
    agents = agent_registry.get_all_agents()
    online_count = sum(
        1 for a in agents
        if a.status.value in {"IDLE", "BUSY"}
    )

    # Get total queue depth
    depths = await queue_manager.get_all_queue_depths()
    total_depth = sum(depths.values())

    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        agents_online=online_count,
        total_queue_depth=total_depth,
    )


from pydantic import BaseModel
class DemoTestRequest(BaseModel):
    user_story: str
    story_title: str

@router.post("/generate-demo-tests")
async def generate_demo_tests(request: DemoTestRequest):
    """
    Direct synchronous endpoint for demo flow to bypass the async queue
    and get real AI-generated test cases instantly.
    """
    from multi_agent_engine.agents.llm_client import LLMClient
    
    # We use a combined prompt for speed instead of the full 6-agent chain
    system_prompt = """You are an expert QA TestGeneratorAgent.
Your task is to generate comprehensive test cases based on the provided user story.

You MUST respond with valid JSON matching exactly this schema:
{
    "test_cases": [
        {
            "test_id": "uuid-string (generate a random uuid4)",
            "title": "Short descriptive title",
            "status": "PASS",
            "preconditions": ["List of preconditions"],
            "steps": [
                {
                    "step_number": 1,
                    "action": "Description of action",
                    "expected_result": "Description of expected result"
                }
            ],
            "expected_result": "Overall expected result",
            "tags": ["functional", "ui", "smoke", etc]
        }
    ]
}

Rules:
- Generate exactly 5-8 high-quality tests
- Include functional, edge case, and negative tests
- Make steps highly specific to the user story provided
- Return ONLY valid JSON, no markdown fences or other text.
"""
    
    user_prompt = f"User Story Title: {request.story_title}\n\nDescription: {request.user_story}"
    
    try:
        client = LLMClient()
        response = await client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout=45,
            temperature=0.7
        )
        
        if not response.success:
            logger.error(f"Vertex AI failed: {response.error}")
            raise HTTPException(status_code=500, detail=response.error)
            
        import json
        data = json.loads(response.content)
        return {"tests": data.get("test_cases", [])}
        
    except Exception as e:
        logger.error(f"Generate demo tests failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
