"""Job routes - handles job submission, status queries, and cancellation."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_service.database import get_db_session
from orchestrator_service.models import Job, JobStatus, TaskType
from orchestrator_service.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobDetailResponse,
    JobSummary,
    JobListResponse,
    CancelResponse,
    StageInfo,
    TaskGraphSummary,
)
from orchestrator_service.services import (
    TaskGraphBuilder,
    GraphBuildError,
    StateManager,
    DependencyResolver,
    TaskScheduler,
    CancellationHandler,
    CancellationError,
    ResultAggregator,
    EventEmitter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/v1/jobs", tags=["jobs"])


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in get_db_session():
        yield session


async def get_state_manager(db: AsyncSession = Depends(get_db)) -> StateManager:
    """Get state manager instance."""
    return StateManager(db)


async def get_graph_builder(db: AsyncSession = Depends(get_db)) -> TaskGraphBuilder:
    """Get task graph builder instance."""
    return TaskGraphBuilder(db)


async def get_scheduler(
    db: AsyncSession = Depends(get_db),
    state_manager: StateManager = Depends(get_state_manager),
) -> TaskScheduler:
    """Get task scheduler instance."""
    return TaskScheduler(db, state_manager)


async def get_event_emitter() -> EventEmitter:
    """Get event emitter instance."""
    return EventEmitter()


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    graph_builder: TaskGraphBuilder = Depends(get_graph_builder),
    state_manager: StateManager = Depends(get_state_manager),
    scheduler: TaskScheduler = Depends(get_scheduler),
    event_emitter: EventEmitter = Depends(get_event_emitter),
):
    """
    Submit a new job for processing.

    Creates the job record, builds the task graph, and schedules
    initial tasks for execution.
    """
    # Check for duplicate job_id
    existing = await state_manager.get_job(request.job_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job with ID {request.job_id} already exists",
        )

    try:
        # Create job record
        job = Job(
            job_id=request.job_id,
            story_title=request.story_title,
            user_story=request.user_story,
            project_id=request.project_id,
            caller_id=request.caller_id,
            priority=request.priority,
            tags=request.tags,
            environment_target=request.environment_target,
            file_ids=request.file_ids,
            status=JobStatus.QUEUED,
        )
        db.add(job)
        await db.flush()

        # Build task graph
        task_graph = await graph_builder.build_graph(job)

        # Emit job queued event
        await event_emitter.emit_job_queued(job)

        # Get root tasks (no dependencies)
        root_tasks = graph_builder.get_root_tasks(task_graph)

        # Schedule root tasks and transition to PROCESSING
        if root_tasks:
            await scheduler.schedule_tasks(root_tasks, job.priority)
            await state_manager.set_job_processing(job)
            await event_emitter.emit_job_processing(job)

        await db.commit()

        # Estimate completion time
        estimated_seconds = await scheduler.estimate_completion_time(
            len(task_graph.tasks),
            job.priority,
        )

        return JobCreateResponse(
            job_id=job.job_id,
            status=job.status,
            queued_at=job.created_at,
            estimated_completion_seconds=estimated_seconds,
        )

    except GraphBuildError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to build task graph: {e.message}",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job",
        )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed status of a specific job.

    Returns job metadata, current status, and task graph summary.
    """
    stmt = select(Job).where(Job.job_id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Build stage information
    stages = []
    task_graph_summary = None

    if job.task_graph:
        aggregator = ResultAggregator()
        summary = aggregator.get_summary(job.task_graph)

        task_graph_summary = TaskGraphSummary(
            task_graph_id=job.task_graph.task_graph_id,
            total_tasks=summary["total_tasks"],
            completed_tasks=summary["status_counts"]["complete"],
            failed_tasks=summary["status_counts"]["failed"],
            progress_percent=summary["progress_percent"],
        )

        # Build stage info from tasks
        for task in job.task_graph.tasks:
            stages.append(
                StageInfo(
                    name=task.task_type.value,
                    status=task.status.value,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                )
            )

    return JobDetailResponse(
        job_id=job.job_id,
        story_title=job.story_title,
        status=job.status,
        project_id=job.project_id,
        caller_id=job.caller_id,
        priority=job.priority,
        environment_target=job.environment_target,
        tags=job.tags or [],
        error_reason=job.error_reason,
        stages=stages,
        task_graph_summary=task_graph_summary,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List jobs with optional filtering and pagination.
    """
    # Build query
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    if project_id:
        query = query.where(Job.project_id == project_id)
        count_query = count_query.where(Job.project_id == project_id)

    if status_filter:
        query = query.where(Job.status == status_filter)
        count_query = count_query.where(Job.status == status_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[
            JobSummary(
                job_id=job.job_id,
                story_title=job.story_title,
                status=job.status,
                project_id=job.project_id,
                priority=job.priority,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{job_id}/cancel", response_model=CancelResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    state_manager: StateManager = Depends(get_state_manager),
    event_emitter: EventEmitter = Depends(get_event_emitter),
):
    """
    Cancel a job.

    Only jobs in QUEUED, PROCESSING, or AWAITING_EXECUTION status
    can be cancelled.
    """
    # Get job
    job = await state_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Check if can cancel
    if not job.can_cancel():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job in {job.status.value} status",
        )

    try:
        # Create dependency resolver for cancellation
        dependency_resolver = DependencyResolver(db, state_manager)
        cancellation_handler = CancellationHandler(db, state_manager, dependency_resolver)

        # Cancel the job
        await cancellation_handler.cancel_job(job)
        await db.commit()

        # Emit cancellation event
        await event_emitter.emit_job_cancelled(job)

        return CancelResponse(
            cancelled=True,
            final_status=job.status.value,
            message="Job cancelled successfully",
        )

    except CancellationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Failed to cancel job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job",
        )
