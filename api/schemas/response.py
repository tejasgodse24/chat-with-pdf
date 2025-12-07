"""
Response schemas for API endpoints.
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional


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


class RetrievedChunk(BaseModel):
    """Schema for a single retrieved chunk"""
    chunk_id: str
    file_id: str
    chunk_text: str
    similarity_score: float


class ChatResponse(BaseModel):
    """Response schema for chat endpoint"""
    conversation_id: UUID
    response: str
    retrieval_mode: str  # "inline" or "rag"
    retrieved_chunks: List[RetrievedChunk] = []


class MessageResponse(BaseModel):
    """Response schema for a single message"""
    role: str  # "user" or "assistant"
    content: str
    file_id: Optional[UUID] = None
    retrieval_mode: Optional[str] = None
    retrieved_chunks: Optional[List[RetrievedChunk]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Response schema for conversation summary (in list view)"""
    conversation_id: UUID
    created_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    """Response schema for paginated conversation list"""
    chats: List[ConversationSummary]
    total: int
    limit: int
    offset: int


class ConversationDetailResponse(BaseModel):
    """Response schema for conversation detail with all messages"""
    conversation_id: UUID
    created_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


class RetrieveResponse(BaseModel):
    """Response schema for retrieve endpoint"""
    results: List[RetrievedChunk]
