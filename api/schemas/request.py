"""
Request Pydantic models for API endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from typing import Optional, List


class PresignRequest(BaseModel):
    """Request model for presigned URL generation"""
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the PDF file to upload (must be a .pdf file)",
        example="document.pdf"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_pdf_extension(cls, v: str) -> str:
        """Validate that filename has .pdf extension"""
        if not v.lower().endswith('.pdf'):
            raise ValueError('Only PDF files are allowed. Filename must end with .pdf')
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(char in v for char in invalid_chars):
            raise ValueError(f'Filename contains invalid characters: {invalid_chars}')
        
        return v


class WebhookIngestRequest(BaseModel):
    """Request model for S3 upload webhook notification"""
    s3_bucket: str = Field(
        ...,
        description="S3 bucket name where file was uploaded",
        example="swe-test-tejas-godse-pdfs"
    )
    s3_key: str = Field(
        ...,
        description="S3 object key (path) of the uploaded file",
        example="uploads/cacc19ff-21f8-4894-bd24-ca93d8c4de4a.pdf"
    )


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User's message/question",
        example="What is this document about?"
    )
    conversation_id: Optional[UUID] = Field(
        None,
        description="Optional conversation ID. If not provided, a new conversation is created.",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    file_id: Optional[UUID] = Field(
        None,
        description="Optional file ID to attach to this message",
        example="cacc19ff-21f8-4894-bd24-ca93d8c4de4a"
    )


class RetrieveRequest(BaseModel):
    """Request model for retrieve endpoint"""
    file_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of file UUIDs to search in",
        example=["cacc19ff-21f8-4894-bd24-ca93d8c4de4a"]
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        example="What is machine learning?"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top results to return (default: 5, max: 20)",
        example=5
    )
