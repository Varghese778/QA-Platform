"""AgentRunner - Executes individual agent: builds prompt, calls LLM, parses output."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import (
    TaskType,
    TaskStatus,
    FailureCategory,
    TaskQueueEntry,
)
from multi_agent_engine.agents.prompt_builder import PromptBuilder
from multi_agent_engine.agents.output_parser import OutputParser, OutputParseError
from multi_agent_engine.agents.llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AgentResult:
    """Result of agent execution."""

    task_id: UUID
    job_id: UUID
    status: TaskStatus
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_category: Optional[FailureCategory] = None
    agent_id: Optional[UUID] = None
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    completed_at: datetime = None

    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)


class AgentRunner:
    """
    Executes a single agent task.

    Workflow:
    1. Build prompt from task payload and context
    2. Call LLM
    3. Parse and validate output
    4. Return structured result
    """

    def __init__(
        self,
        agent_id: UUID,
        prompt_builder: Optional[PromptBuilder] = None,
        output_parser: Optional[OutputParser] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.agent_id = agent_id
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.output_parser = output_parser or OutputParser()
        self.llm_client = llm_client or LLMClient()

    async def execute(
        self,
        task_entry: TaskQueueEntry,
        repair_attempt: bool = False,
    ) -> AgentResult:
        """
        Execute a task and return the result.

        Args:
            task_entry: The task to execute.
            repair_attempt: Whether this is a JSON repair retry.

        Returns:
            AgentResult with output or error.
        """
        start_time = time.time()

        try:
            # Build prompts
            system_prompt, user_prompt = self.prompt_builder.build_prompt(
                task_entry.task_type,
                task_entry.payload,
                task_entry.context,
            )

            # Add repair instruction if needed
            if repair_attempt:
                user_prompt = self.prompt_builder.add_json_repair_instruction(user_prompt)

            # Configure model
            model = settings.llm_default_model
            if task_entry.model_config_data and "model" in task_entry.model_config_data:
                model = task_entry.model_config_data["model"]

            # Call LLM
            llm_response = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                timeout=task_entry.timeout_seconds,
            )

            if not llm_response.success:
                return AgentResult(
                    task_id=task_entry.task_id,
                    job_id=task_entry.job_id,
                    status=TaskStatus.FAILED,
                    error_message=llm_response.error,
                    error_category=llm_response.error_category,
                    agent_id=self.agent_id,
                    model_used=llm_response.model,
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    latency_ms=llm_response.latency_ms,
                )

            # Parse and validate output
            try:
                output = self.output_parser.parse(
                    task_entry.task_type,
                    llm_response.content,
                )
            except OutputParseError as e:
                # If this isn't already a repair attempt, signal for retry
                return AgentResult(
                    task_id=task_entry.task_id,
                    job_id=task_entry.job_id,
                    status=TaskStatus.FAILED,
                    error_message=e.message,
                    error_category=e.category,
                    agent_id=self.agent_id,
                    model_used=llm_response.model,
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    latency_ms=llm_response.latency_ms,
                )

            # Success
            latency_ms = int((time.time() - start_time) * 1000)

            return AgentResult(
                task_id=task_entry.task_id,
                job_id=task_entry.job_id,
                status=TaskStatus.COMPLETE,
                output=output,
                agent_id=self.agent_id,
                model_used=llm_response.model,
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            latency_ms = int((time.time() - start_time) * 1000)

            return AgentResult(
                task_id=task_entry.task_id,
                job_id=task_entry.job_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                error_category=FailureCategory.INTERNAL_ERROR,
                agent_id=self.agent_id,
                latency_ms=latency_ms,
            )
