"""
Response Pydantic models for API endpoints.
"""
from pydantic import BaseModel, Field
from uuid import UUID


class PresignResponse(BaseModel):
    """Response model for presigned URL generation"""
    file_id: UUID = Field(
        ...,
        description="Unique identifier for the uploaded file"
    )
    presigned_url: str = Field(
        ...,
        description="Presigned S3 URL for uploading the file"
    )
    expires_in_seconds: int = Field(
        ...,
        description="Number of seconds until the presigned URL expires",
        example=3600
    )
