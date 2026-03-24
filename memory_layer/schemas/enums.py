"""Enum definitions for Memory Layer."""

from enum import Enum


class RecordType(str, Enum):
    """Types of memory records."""

    TEST_CASE = "TEST_CASE"
    PATTERN = "PATTERN"
    CONSTRAINT = "CONSTRAINT"
    ENTITY = "ENTITY"


class TestResultType(str, Enum):
    """Test execution result types."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class ConstraintScope(str, Enum):
    """Scope of a constraint."""

    GLOBAL = "GLOBAL"
    DOMAIN = "DOMAIN"
    ACTOR = "ACTOR"


class ConstraintPriority(str, Enum):
    """Constraint priority level."""

    HARD = "HARD"  # Must not violate
    SOFT = "SOFT"  # Prefer to respect


class EntityType(str, Enum):
    """Types of entities in knowledge graph."""

    ACTOR = "ACTOR"
    SYSTEM = "SYSTEM"
    DATABASE = "DATABASE"
    SERVICE = "SERVICE"
    DATA_OBJECT = "DATA_OBJECT"


class TestDomain(str, Enum):
    """Test domain classifications."""

    UI = "UI"
    API = "API"
    DATABASE = "DATABASE"
    AUTH = "AUTH"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
