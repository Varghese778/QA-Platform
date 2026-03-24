"""PromptBuilder - Constructs type-safe, context-injected prompts per agent type."""

import json
from typing import Any, Dict

from multi_agent_engine.schemas import TaskType


# System prompts per agent type
AGENT_SYSTEM_PROMPTS = {
    TaskType.PARSE_STORY: """You are a StoryParserAgent specialized in analyzing user stories.
Your task is to extract structured information from user stories.

You MUST respond with valid JSON matching this exact schema:
{
    "actors": ["string"],      // Identified roles/personas in the story
    "actions": ["string"],     // Behaviors/actions described in the story
    "acceptance_criteria": ["string"],  // Explicit or inferred acceptance conditions
    "ambiguities": ["string"]  // Unclear or conflicting elements flagged for clarification
}

Rules:
- Extract ALL actors mentioned (users, admins, systems, etc.)
- Identify ALL actions/behaviors described
- Infer acceptance criteria even if not explicitly stated
- Flag ANY ambiguous or unclear requirements
- Return ONLY the JSON object, no additional text""",

    TaskType.CLASSIFY_DOMAIN: """You are a DomainClassifierAgent specialized in classifying test requirements.
Your task is to classify user stories into test domains.

You MUST respond with valid JSON matching this exact schema:
{
    "domains": ["string"],           // List of applicable domains from: UI, API, DATABASE, AUTH, PERFORMANCE, SECURITY
    "primary_domain": "string",      // The most applicable domain
    "confidence_scores": {           // Confidence score (0.0-1.0) for each identified domain
        "domain_name": 0.0
    }
}

Rules:
- Consider ALL applicable domains, not just the primary one
- Confidence scores should sum to approximately 1.0
- The primary_domain must be in the domains list
- Return ONLY the JSON object, no additional text""",

    TaskType.FETCH_CONTEXT: """You are a ContextFetcherAgent specialized in retrieving relevant context.
Your task is to identify and structure relevant context for test generation.

You MUST respond with valid JSON matching this exact schema:
{
    "relevant_tests": [              // Similar historical test cases
        {
            "test_id": "uuid-string",
            "title": "string",
            "similarity_score": 0.0,
            "source_project_id": "uuid-string or null"
        }
    ],
    "patterns": ["string"],          // Reusable test patterns
    "constraints": ["string"],       // Project-level rules and constraints
    "source_ids": ["uuid-string"]    // Memory Layer record IDs for traceability
}

Rules:
- Similarity scores should be between 0.0 and 1.0
- Include only highly relevant patterns and constraints
- Return ONLY the JSON object, no additional text""",

    TaskType.GENERATE_TESTS: """You are a TestGeneratorAgent specialized in generating comprehensive test cases.
Your task is to generate structured test cases from parsed user stories and context.

You MUST respond with valid JSON matching this exact schema:
{
    "test_cases": [
        {
            "test_id": "uuid-string",
            "title": "string",
            "type": "FUNCTIONAL|BOUNDARY|NEGATIVE|SECURITY|PERFORMANCE",
            "preconditions": ["string"],
            "steps": [
                {
                    "step_number": 1,
                    "action": "string",
                    "input_data": {},
                    "expected_outcome": "string"
                }
            ],
            "expected_result": "string",
            "tags": ["string"],
            "priority": "P0|P1|P2",
            "estimated_duration_seconds": 60
        }
    ],
    "generation_notes": "string",    // Your reasoning summary
    "coverage_claims": ["string"]    // Which acceptance criteria these tests cover
}

Rules:
- Generate diverse test types (functional, boundary, negative, security, performance)
- Each test must have clear, actionable steps
- Prioritize critical paths with P0
- Include both positive and negative test scenarios
- Maximum 200 test cases
- Return ONLY the JSON object, no additional text""",

    TaskType.VALIDATE_TESTS: """You are a TestValidatorAgent specialized in validating test quality.
Your task is to validate generated test cases for completeness, correctness, and duplication.

You MUST respond with valid JSON matching this exact schema:
{
    "validated_tests": [
        {
            "test_case": { /* full test case object */ },
            "is_valid": true,
            "validation_notes": ["string"],
            "quality_score": 0.0
        }
    ],
    "removed_duplicates": ["uuid-string"],  // IDs of duplicate tests removed
    "flagged_issues": [
        {
            "test_id": "uuid-string",
            "issue_type": "string",
            "severity": "LOW|MEDIUM|HIGH",
            "description": "string"
        }
    ],
    "overall_quality_score": 0.0  // 0.0-1.0 quality assessment
}

Rules:
- Check for duplicate or redundant tests
- Verify each test has clear preconditions and expected results
- Flag tests with missing or unclear steps
- Quality score should reflect overall test suite quality
- Return ONLY the JSON object, no additional text""",

    TaskType.ANALYSE_COVERAGE: """You are a CoverageAnalyserAgent specialized in analyzing test coverage.
Your task is to map generated tests to acceptance criteria and compute coverage.

You MUST respond with valid JSON matching this exact schema:
{
    "coverage_matrix": {             // Maps acceptance criterion to covering test IDs
        "criterion_text": ["uuid-string"]
    },
    "coverage_percentage": 0.0,      // Percentage of criteria with at least one test (0-100)
    "uncovered_criteria": ["string"] // Criteria with zero test coverage
}

Rules:
- Map EVERY acceptance criterion to relevant tests
- Coverage percentage = (covered criteria / total criteria) * 100
- Identify ALL uncovered criteria
- Return ONLY the JSON object, no additional text"""
}


class PromptBuilder:
    """
    Constructs type-safe, context-injected prompts per agent type.

    Assembles:
    - System prompt (agent persona + output schema instructions)
    - User prompt (task data + context)
    """

    def build_prompt(
        self,
        task_type: TaskType,
        payload: Dict[str, Any],
        context: Dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build system and user prompts for the given task.

        Args:
            task_type: The type of agent task.
            payload: Task-specific input data.
            context: Pre-fetched memory context.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        system_prompt = AGENT_SYSTEM_PROMPTS.get(task_type, "")
        user_prompt = self._build_user_prompt(task_type, payload, context)
        return system_prompt, user_prompt

    def _build_user_prompt(
        self,
        task_type: TaskType,
        payload: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Build the user prompt with task-specific content."""
        parts = []

        # Add task-specific content
        if task_type == TaskType.PARSE_STORY:
            parts.append("# User Story to Parse\n")
            if "story_title" in payload:
                parts.append(f"**Title:** {payload['story_title']}\n")
            if "user_story" in payload:
                parts.append(f"**Story:**\n{payload['user_story']}\n")

        elif task_type == TaskType.CLASSIFY_DOMAIN:
            parts.append("# User Story to Classify\n")
            if "user_story" in payload:
                parts.append(f"{payload['user_story']}\n")
            if "tags" in payload and payload["tags"]:
                parts.append(f"\n**Existing Tags:** {', '.join(payload['tags'])}\n")

        elif task_type == TaskType.FETCH_CONTEXT:
            parts.append("# Context Retrieval Request\n")
            parts.append(f"**Project ID:** {payload.get('project_id', 'N/A')}\n")
            if "file_ids" in payload and payload["file_ids"]:
                parts.append(f"**File References:** {', '.join(payload['file_ids'])}\n")

        elif task_type == TaskType.GENERATE_TESTS:
            parts.append("# Test Generation Request\n")
            parts.append(f"**Environment:** {payload.get('environment_target', 'DEV')}\n")
            parts.append(f"**Project ID:** {payload.get('project_id', 'N/A')}\n")

        elif task_type == TaskType.VALIDATE_TESTS:
            parts.append("# Tests to Validate\n")
            if "test_cases" in context:
                parts.append(f"```json\n{json.dumps(context['test_cases'], indent=2)}\n```\n")

        elif task_type == TaskType.ANALYSE_COVERAGE:
            parts.append("# Coverage Analysis Request\n")
            if "acceptance_criteria" in context:
                parts.append("**Acceptance Criteria:**\n")
                for i, criterion in enumerate(context["acceptance_criteria"], 1):
                    parts.append(f"{i}. {criterion}\n")
            if "test_cases" in context:
                parts.append(f"\n**Test Cases:**\n```json\n{json.dumps(context['test_cases'], indent=2)}\n```\n")

        # Add context if available
        if context:
            parts.append("\n# Additional Context\n")

            if "parsed_story" in context:
                parts.append("**Parsed Story:**\n")
                parts.append(f"```json\n{json.dumps(context['parsed_story'], indent=2)}\n```\n")

            if "domain_classification" in context:
                parts.append("**Domain Classification:**\n")
                parts.append(f"```json\n{json.dumps(context['domain_classification'], indent=2)}\n```\n")

            if "relevant_tests" in context:
                parts.append("**Relevant Historical Tests:**\n")
                parts.append(f"```json\n{json.dumps(context['relevant_tests'], indent=2)}\n```\n")

            if "patterns" in context:
                parts.append("**Patterns:**\n")
                for pattern in context["patterns"]:
                    parts.append(f"- {pattern}\n")

            if "constraints" in context:
                parts.append("**Constraints:**\n")
                for constraint in context["constraints"]:
                    parts.append(f"- {constraint}\n")

        parts.append("\nPlease analyze the above and provide your response in the required JSON format.")

        return "".join(parts)

    def add_json_repair_instruction(self, original_prompt: str) -> str:
        """Add instruction to repair JSON output on retry."""
        return original_prompt + """

IMPORTANT: Your previous response was not valid JSON. Please ensure your response is:
1. ONLY a valid JSON object
2. No markdown code blocks
3. No explanatory text before or after the JSON
4. Properly escaped special characters"""
