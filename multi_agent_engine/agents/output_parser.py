"""OutputParser - Deserializes and validates LLM responses against output schemas."""

import json
import logging
import re
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ValidationError

from multi_agent_engine.schemas import (
    TaskType,
    FailureCategory,
    TASK_OUTPUT_SCHEMAS,
)

logger = logging.getLogger(__name__)


class OutputParseError(Exception):
    """Raised when output parsing fails."""

    def __init__(
        self,
        message: str,
        category: FailureCategory = FailureCategory.OUTPUT_PARSE_ERROR,
        raw_output: Optional[str] = None,
    ):
        self.message = message
        self.category = category
        self.raw_output = raw_output
        super().__init__(message)


class OutputParser:
    """
    Deserializes and validates LLM responses against per-task output schemas.
    """

    def parse(
        self,
        task_type: TaskType,
        raw_output: str,
    ) -> Dict[str, Any]:
        """
        Parse and validate LLM output.

        Args:
            task_type: The task type to validate against.
            raw_output: Raw string output from LLM.

        Returns:
            Validated output as dictionary.

        Raises:
            OutputParseError: If parsing or validation fails.
        """
        # Get the schema class for this task type
        schema_class = TASK_OUTPUT_SCHEMAS.get(task_type.value)
        if not schema_class:
            raise OutputParseError(
                f"No schema defined for task type {task_type.value}",
                category=FailureCategory.SCHEMA_MISMATCH,
            )

        # Extract JSON from response
        json_str = self._extract_json(raw_output)
        if not json_str:
            raise OutputParseError(
                "Could not extract JSON from LLM response",
                category=FailureCategory.OUTPUT_PARSE_ERROR,
                raw_output=raw_output[:500],  # Truncate for logging
            )

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise OutputParseError(
                f"Invalid JSON: {str(e)}",
                category=FailureCategory.OUTPUT_PARSE_ERROR,
                raw_output=json_str[:500],
            )

        # Validate against schema
        try:
            validated = schema_class.model_validate(data)
            return validated.model_dump()
        except ValidationError as e:
            raise OutputParseError(
                f"Schema validation failed: {str(e)}",
                category=FailureCategory.SCHEMA_MISMATCH,
                raw_output=json_str[:500],
            )

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extract JSON object from text that may contain other content.

        Handles:
        - Raw JSON
        - JSON in markdown code blocks
        - JSON with leading/trailing text
        """
        text = text.strip()

        # Try raw JSON first
        if text.startswith("{") and text.endswith("}"):
            return text

        # Try to extract from markdown code block
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if code_block_match:
            return code_block_match.group(1).strip()

        # Try to find JSON object in text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0)

        return None

    def validate_schema(
        self,
        task_type: TaskType,
        data: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Validate data against schema without parsing.

        Returns:
            Tuple of (is_valid, error_message).
        """
        schema_class = TASK_OUTPUT_SCHEMAS.get(task_type.value)
        if not schema_class:
            return False, f"No schema for task type {task_type.value}"

        try:
            schema_class.model_validate(data)
            return True, None
        except ValidationError as e:
            return False, str(e)
