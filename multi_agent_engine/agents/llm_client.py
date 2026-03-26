"""LLMClient - Manages LLM API calls with retry, timeout, and token tracking."""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from multi_agent_engine.config import get_settings
from multi_agent_engine.schemas import TaskType, FailureCategory

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Vertex AI if provider is vertex-ai
if settings.llm_provider == "vertex-ai":
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        # Set credentials path
        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

        # Initialize Vertex AI
        if settings.gcp_project_id:
            vertexai.init(project=settings.gcp_project_id, location=settings.gcp_location)
            logger.info(f"Vertex AI initialized: project={settings.gcp_project_id}, location={settings.gcp_location}")
        else:
            logger.warning("GCP_PROJECT_ID not set, Vertex AI initialization skipped")
    except ImportError:
        logger.error("google-cloud-aiplatform not installed. Install with: pip install google-cloud-aiplatform")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")


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
            elif settings.llm_provider == "vertex-ai":
                response = await self._real_generate(
                    system_prompt, user_prompt, model, temperature, max_tokens, timeout
                )
            else:
                # Production: call actual LLM API (OpenAI, Anthropic, etc.)
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
                        "source_project_id": str(uuid.uuid4()),
                        "last_result": "PASS",
                        "run_count": 23,
                    },
                    {
                        "test_id": str(uuid.uuid4()),
                        "title": "Session persistence after browser close",
                        "similarity_score": 0.78,
                        "source_project_id": str(uuid.uuid4()),
                        "last_result": "FAIL",
                        "run_count": 15,
                    },
                ],
                "historical_defects": [
                    {
                        "defect_id": "DEF-2026-031",
                        "title": "Login timeout under high concurrency",
                        "severity": "CRITICAL",
                        "sprint": "Sprint 12",
                        "resolution": "Connection pooling fix",
                        "recurrence_risk": 0.35,
                    },
                    {
                        "defect_id": "DEF-2026-028",
                        "title": "Session lost after browser restart",
                        "severity": "HIGH",
                        "sprint": "Sprint 11",
                        "resolution": "LocalStorage fallback added",
                        "recurrence_risk": 0.22,
                    },
                ],
                "regression_patterns": [
                    {
                        "pattern_id": "REG-2026-007",
                        "description": "CSRF protection regressions in 2 of last 4 releases",
                        "affected_area": "Authentication",
                        "risk_level": "HIGH",
                    },
                ],
                "patterns": [
                    "Form validation pattern",
                    "Authentication flow pattern",
                    "Session management pattern",
                ],
                "constraints": [
                    "Must test against staging environment",
                    "Use test user accounts only",
                ],
                "knowledge_graph_context": {
                    "entities_consulted": 12,
                    "relationships_traversed": 8,
                    "flow_chain": "Login → Session → Dashboard → Profile",
                },
                "source_ids": [str(uuid.uuid4())],
                "learning_metadata": {
                    "total_historical_runs_analyzed": 47,
                    "defects_consulted": 12,
                    "knowledge_base_queries": 8,
                    "context_relevance_score": 0.92,
                },
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

    @staticmethod
    def _extract_json(text: str) -> str:
        """
        Extract JSON from LLM response text.
        
        Gemini sometimes wraps JSON in markdown code fences like:
          ```json
          {...}
          ```
        This method strips those fences to get clean JSON.
        """
        import re

        text = text.strip()

        # Remove markdown code fences: ```json ... ``` or ``` ... ```
        md_match = re.match(r'^```(?:json)?\s*\n?(.*?)\n?\s*```$', text, re.DOTALL)
        if md_match:
            text = md_match.group(1).strip()

        # Validate it's parseable JSON
        try:
            json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"LLM response is not valid JSON (first 200 chars): {text[:200]}")

        return text

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
        Real LLM API call using Vertex AI.

        Integrates with Google Cloud Vertex AI Gemini models.
        """
        if settings.llm_provider != "vertex-ai":
            logger.warning(f"Provider {settings.llm_provider} not supported, falling back to mock")
            return await self._mock_generate(system_prompt, user_prompt, model, timeout)

        try:
            # Initialize the Gemini model
            vertex_model = GenerativeModel(model or settings.llm_default_model)

            # Combine system and user prompts — instruct JSON output
            full_prompt = (
                f"{system_prompt}\n\n"
                f"IMPORTANT: You MUST respond with valid JSON only. "
                f"Do NOT wrap in markdown code fences. Do NOT add any text before or after the JSON.\n\n"
                f"{user_prompt}"
            )

            # Configure generation parameters
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=0.95,
                top_k=40,
                response_mime_type="application/json",
            )

            # Generate content asynchronously
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    vertex_model.generate_content,
                    full_prompt,
                    generation_config=generation_config,
                ),
                timeout=timeout,
            )

            # Extract response text and clean it
            content = self._extract_json(response.text)

            # Extract usage metadata (estimate if not available)
            prompt_tokens = len(full_prompt.split())  # Rough approximation
            completion_tokens = len(content.split())

            # Try to get actual usage if available
            if hasattr(response, 'usage_metadata'):
                prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', prompt_tokens)
                completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', completion_tokens)

            return LLMResponse(
                content=content,
                model=model or settings.llm_default_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=0,  # Will be set by caller
                success=True,
            )

        except asyncio.TimeoutError:
            logger.error(f"Vertex AI request timed out after {timeout}s")
            return LLMResponse(
                content="",
                model=model or settings.llm_default_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                success=False,
                error="Request timed out",
                error_category=FailureCategory.TIMEOUT,
            )
        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}", exc_info=True)
            return LLMResponse(
                content="",
                model=model or settings.llm_default_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                success=False,
                error=str(e),
                error_category=FailureCategory.LLM_API_ERROR,
            )
