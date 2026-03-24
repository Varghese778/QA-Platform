"""Upload-related schemas."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UploadError(BaseModel):
    """Error for a single file upload."""

    filename: str = Field(..., description="Name of the file that failed")
    error: str = Field(..., description="Error description")


class UploadResponse(BaseModel):
    """Response after uploading files."""

    file_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs of successfully uploaded files",
    )
    errors: List[UploadError] = Field(
        default_factory=list,
        description="Errors for failed uploads",
    )
