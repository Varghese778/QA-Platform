"""Enum definitions for Artifact Storage."""

from enum import Enum


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""

    CONTEXT_FILE = "CONTEXT_FILE"
    TEST_RESULT = "TEST_RESULT"
    TEST_REPORT = "TEST_REPORT"
    SCREENSHOT = "SCREENSHOT"
    LOG_FILE = "LOG_FILE"
    COVERAGE_REPORT = "COVERAGE_REPORT"
    EXPORT = "EXPORT"


class ScanStatus(str, Enum):
    """Virus scan status."""

    PENDING = "PENDING"
    SCANNING = "SCANNING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    SCAN_ERROR = "SCAN_ERROR"


class ArtifactStatus(str, Enum):
    """Artifact lifecycle status."""

    UPLOADING = "UPLOADING"
    AVAILABLE = "AVAILABLE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class ExportFormat(str, Enum):
    """Export format types."""

    ZIP = "ZIP"
    TAR_GZ = "TAR_GZ"
    JSON = "JSON"
