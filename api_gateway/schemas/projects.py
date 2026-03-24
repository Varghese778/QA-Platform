"""Project-related schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    """Project information."""

    project_id: UUID = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    org_id: UUID = Field(..., description="Owning organization ID")
    member_count: int = Field(..., description="Number of project members")
    created_at: datetime = Field(..., description="Creation timestamp")


class ProjectListResponse(BaseModel):
    """List of projects."""

    projects: List[ProjectResponse] = Field(default_factory=list)
