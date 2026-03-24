"""Schemas package - exports all Pydantic schemas."""

from api_gateway.schemas.common import (
    ErrorEnvelope,
    ErrorDetail,
    HealthResponse,
    ReadyResponse,
    DependencyStatus,
)
from api_gateway.schemas.jobs import (
    JobSubmitRequest,
    JobSubmitResponse,
    JobListResponse,
    JobItem,
    JobDetailResponse,
    JobCancelResponse,
    JobTestsResponse,
    TestCase,
    JobReportResponse,
    ReportSummary,
    Failure,
)
from api_gateway.schemas.projects import (
    ProjectListResponse,
    ProjectResponse,
)
from api_gateway.schemas.uploads import (
    UploadResponse,
    UploadError,
)
from api_gateway.schemas.access_log import AccessLogRecord

__all__ = [
    # Common
    "ErrorEnvelope",
    "ErrorDetail",
    "HealthResponse",
    "ReadyResponse",
    "DependencyStatus",
    # Jobs
    "JobSubmitRequest",
    "JobSubmitResponse",
    "JobListResponse",
    "JobItem",
    "JobDetailResponse",
    "JobCancelResponse",
    "JobTestsResponse",
    "TestCase",
    "JobReportResponse",
    "ReportSummary",
    "Failure",
    # Projects
    "ProjectListResponse",
    "ProjectResponse",
    # Uploads
    "UploadResponse",
    "UploadError",
    # Access Log
    "AccessLogRecord",
]
