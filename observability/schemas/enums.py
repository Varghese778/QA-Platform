"""Enum definitions for Observability & Logging."""

from enum import Enum


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(str, Enum):
    """Types of metrics."""

    COUNTER = "COUNTER"  # Monotonically increasing
    GAUGE = "GAUGE"  # Point-in-time value
    HISTOGRAM = "HISTOGRAM"  # Distribution
    SUMMARY = "SUMMARY"  # Aggregated summary


class SpanStatus(str, Enum):
    """Distributed trace span status."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Alert status."""

    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    SILENCED = "SILENCED"


class ComparisonOperator(str, Enum):
    """Comparison operators for alert rules."""

    EQ = "EQ"  # Equal
    NEQ = "NEQ"  # Not equal
    GT = "GT"  # Greater than
    GTE = "GTE"  # Greater than or equal
    LT = "LT"  # Less than
    LTE = "LTE"  # Less than or equal
