"""
Response schemas for API endpoints.
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List


class PresignResponse(BaseModel):
    """Response schema for presigned URL generation"""
    file_id: UUID
    presigned_url: str
    expires_in_seconds: int


class FileResponse(BaseModel):
    """Response schema for a single file"""
    file_id: UUID
    s3_key: str
    ingestion_status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Allows creating from ORM models


class FileListResponse(BaseModel):
    """Response schema for paginated file list"""
    files: List[FileResponse]
    total: int
    limit: int
    offset: int


class FileDetailResponse(BaseModel):
    """Response schema for file detail with download URL"""
    file_id: UUID
    s3_key: str
    ingestion_status: str
    presigned_download_url: str
    download_url_expires_in_seconds: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Allows creating from ORM models
