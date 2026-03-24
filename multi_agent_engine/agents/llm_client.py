"""LLMClient - Manages LLM API calls with retry, timeout, and token tracking."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import TaskType, FailureCategory

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class LLMResponse:
    """Response from LLM call."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    success: bool
    error: Optional[str] = None
    error_category: Optional[FailureCategory] = None


class LLMError(Exception):
    """Raised when LLM call fails."""

    def __init__(
        self,
        message: str,
        category: FailureCategory = FailureCategory.LLM_API_ERROR,
    ):
        self.message = message
        self.category = category
        super().__init__(message)


class LLMClient:
    """
    Manages LLM API calls.

    For MVP, provides mock responses that return valid JSON structures.
    In production, would integrate with OpenAI, Anthropic, etc.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.llm_default_model
        self.timeout = settings.llm_timeout_seconds

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            system_prompt: System/persona prompt.
            user_prompt: User message with task content.
            model: Model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            timeout: Timeout override.

        Returns:
            LLMResponse with content and metadata.
        """
        model = model or self.model
        timeout = timeout or self.timeout

        start_time = time.time()

        try:
            if settings.llm_provider == "mock":
                response = await self._mock_generate(
                    system_prompt, user_prompt, model, timeout
                )
            else:
                # Production: call actual LLM API
                response = await self._real_generate(
                    system_prompt, user_prompt, model, temperature, max_tokens, timeout
                )

            latency_ms = int((time.time() - start_time) * 1000)
            response.latency_ms = latency_ms

            logger.debug(
                f"LLM response generated in {latency_ms}ms "
                f"(prompt={response.prompt_tokens}, completion={response.completion_tokens})"
            )

            return response

        except asyncio.TimeoutError:
            latency_ms = int((time.time() - start_time) * 1000)
            return LLMResponse(
                content="",
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error="Request timed out",
                error_category=FailureCategory.TIMEOUT,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return LLMResponse(
                content="",
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
                error_category=FailureCategory.LLM_API_ERROR,
            )

    async def _mock_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int,
    ) -> LLMResponse:
        """Generate mock response based on task type detected from prompt."""
        # Simulate API latency
        await asyncio.sleep(0.5)

        # Detect task type from system prompt
        content = self._get_mock_response(system_prompt)

        # Estimate tokens (rough approximation)
        prompt_tokens = len(system_prompt.split()) + len(user_prompt.split())
        completion_tokens = len(content.split())

        return LLMResponse(
            content=content,
            model=f"mock-{model}",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=0,  # Will be set by caller
            success=True,
        )

    def _get_mock_response(self, system_prompt: str) -> str:
        """Get mock response based on detected agent type."""
        if "StoryParserAgent" in system_prompt:
            return json.dumps({
                "actors": ["User", "System Administrator", "API Client"],
                "actions": [
                    "Login to the application",
                    "View dashboard",
                    "Submit form data",
                    "Receive confirmation"
                ],
                "acceptance_criteria": [
                    "User can successfully log in with valid credentials",
                    "Dashboard loads within 3 seconds",
                    "Form submission returns success message",
                    "Invalid inputs show appropriate error messages"
                ],
                "ambiguities": [
                    "Session timeout duration not specified",
                    "Error message format not defined"
                ]
            })

        elif "DomainClassifierAgent" in system_prompt:
            return json.dumps({
                "domains": ["UI", "API", "AUTH"],
                "primary_domain": "UI",
                "confidence_scores": {
                    "UI": 0.6,
                    "API": 0.25,
                    "AUTH": 0.15
                }
            })

        elif "ContextFetcherAgent" in system_prompt:
            return json.dumps({
                "relevant_tests": [
                    {
                        "test_id": str(uuid.uuid4()),
                        "title": "Login form validation test",
                        "similarity_score": 0.85,
                        "source_project_id": str(uuid.uuid4())
                    }
                ],
                "patterns": [
                    "Form validation pattern",
                    "Authentication flow pattern"
                ],
                "constraints": [
                    "Must test against staging environment",
                    "Use test user accounts only"
                ],
                "source_ids": [str(uuid.uuid4())]
            })

        elif "TestGeneratorAgent" in system_prompt:
            test_id_1 = str(uuid.uuid4())
            test_id_2 = str(uuid.uuid4())
            return json.dumps({
                "test_cases": [
                    {
                        "test_id": test_id_1,
                        "title": "Verify successful login with valid credentials",
                        "type": "FUNCTIONAL",
                        "preconditions": ["User account exists", "User is not logged in"],
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Navigate to login page",
                                "input_data": {"url": "/login"},
                                "expected_outcome": "Login page is displayed"
                            },
                            {
                                "step_number": 2,
                                "action": "Enter valid username",
                                "input_data": {"username": "testuser@example.com"},
                                "expected_outcome": "Username field accepts input"
                            },
                            {
                                "step_number": 3,
                                "action": "Enter valid password",
                                "input_data": {"password": "ValidPass123!"},
                                "expected_outcome": "Password field accepts input"
                            },
                            {
                                "step_number": 4,
                                "action": "Click login button",
                                "input_data": {},
                                "expected_outcome": "User is redirected to dashboard"
                            }
                        ],
                        "expected_result": "User is successfully logged in and sees dashboard",
                        "tags": ["login", "authentication", "smoke"],
                        "priority": "P0",
                        "estimated_duration_seconds": 30
                    },
                    {
                        "test_id": test_id_2,
                        "title": "Verify error message for invalid credentials",
                        "type": "NEGATIVE",
                        "preconditions": ["User account exists"],
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Navigate to login page",
                                "input_data": {"url": "/login"},
                                "expected_outcome": "Login page is displayed"
                            },
                            {
                                "step_number": 2,
                                "action": "Enter invalid credentials and submit",
                                "input_data": {"username": "invalid@test.com", "password": "wrong"},
                                "expected_outcome": "Login attempt fails"
                            }
                        ],
                        "expected_result": "Error message displays: Invalid username or password",
                        "tags": ["login", "error-handling", "negative"],
                        "priority": "P1",
                        "estimated_duration_seconds": 20
                    }
                ],
                "generation_notes": "Generated 2 test cases covering positive and negative login scenarios",
                "coverage_claims": [
                    "User can successfully log in with valid credentials",
                    "Invalid inputs show appropriate error messages"
                ]
            })

        elif "TestValidatorAgent" in system_prompt:
            return json.dumps({
                "validated_tests": [],
                "removed_duplicates": [],
                "flagged_issues": [],
                "overall_quality_score": 0.95
            })

        elif "CoverageAnalyserAgent" in system_prompt:
            return json.dumps({
                "coverage_matrix": {
                    "User can successfully log in": [str(uuid.uuid4())],
                    "Invalid inputs show errors": [str(uuid.uuid4())]
                },
                "coverage_percentage": 75.0,
                "uncovered_criteria": ["Session timeout behavior"]
            })

        else:
            # Default empty response
            return json.dumps({})

    async def _real_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> LLMResponse:
        """
        Real LLM API call (placeholder for production).

        Would integrate with OpenAI, Anthropic, etc.
        """
        # Production implementation would go here
        # For now, fall back to mock
        return await self._mock_generate(system_prompt, user_prompt, model, timeout)
