"""
File model for tracking uploaded PDF files.
"""
from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from .base import Base
from enum import Enum

class IngestionStatus(str, Enum):
    UPLOADED = "uploaded"
    COMPLETED = "completed"
    FAILED = "failed"


class File(Base):
    """
    File model representing uploaded PDF files.
    
    Attributes:
        id: Unique file identifier (UUID)
        name: Original filename provided by user
        s3_key: S3 object key (path) for the file
        ingestion_status: Current processing status
        created_at: Timestamp when file was uploaded
        updated_at: Timestamp when file was last modified
    """
    __tablename__ = "files"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique file identifier"
    )
    
    s3_key = Column(
        String(255),
        nullable=False,
        comment="S3 object key (e.g., uploads/{uuid}.pdf)"
    )
    
    ingestion_status = Column(
        SAEnum(IngestionStatus, name="ingestion_status_enum"),
        nullable=False,
        default=IngestionStatus.UPLOADED,
        comment="Processing status: uploaded, processing, completed, failed"
    )
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when file was uploaded"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp when file was last modified"
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if ingestion failed"
    )

    def __repr__(self):
        return f"<File(id={self.id}, status={self.ingestion_status})>"
