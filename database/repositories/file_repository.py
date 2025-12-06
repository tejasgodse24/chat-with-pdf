"""
File repository for database operations.
Handles all File model database queries.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID

from database.models.file import File, IngestionStatus


class FileRepository:
    """Repository for File model database operations"""
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create(
        self,
        file_id: UUID,
        s3_key: str,
        ingestion_status: IngestionStatus = IngestionStatus.UPLOADED
    ) -> File:
        """
        Create a new file record.
        
        Args:
            file_id: Unique file identifier
            s3_key: S3 object key
            ingestion_status: Initial ingestion status (default: UPLOADED)
        
        Returns:
            Created File object
        """
        db_file = File(
            id=file_id,
            s3_key=s3_key,
            ingestion_status=ingestion_status
        )
        self.db.add(db_file)
        self.db.commit()
        self.db.refresh(db_file)
        return db_file
    
    def get_by_id(self, file_id: UUID) -> Optional[File]:
        """
        Get file by ID.
        
        Args:
            file_id: File UUID
        
        Returns:
            File object or None if not found
        """
        return self.db.query(File).filter(File.id == file_id).first()
    
    def get_all_paginated(self, limit: int = 20, offset: int = 0) -> List[File]:
        """
        Get paginated list of files, ordered by created_at descending.
        
        Args:
            limit: Maximum number of files to return
            offset: Number of files to skip
        
        Returns:
            List of File objects
        """
        return self.db.query(File)\
            .order_by(File.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
    
    def count_all(self) -> int:
        """
        Get total count of all files.
        
        Returns:
            Total number of files
        """
        return self.db.query(func.count(File.id)).scalar()
    
    def update_status(
        self,
        file_id: UUID,
        status: IngestionStatus
    ) -> Optional[File]:
        """
        Update file ingestion status.
        
        Args:
            file_id: File UUID
            status: New ingestion status
        
        Returns:
            Updated File object or None if not found
        """
        db_file = self.get_by_id(file_id)
        if db_file:
            db_file.ingestion_status = status
            self.db.commit()
            self.db.refresh(db_file)
        return db_file
    
    def delete(self, file_id: UUID) -> bool:
        """
        Delete file record.
        
        Args:
            file_id: File UUID
        
        Returns:
            True if deleted, False if not found
        """
        db_file = self.get_by_id(file_id)
        if db_file:
            self.db.delete(db_file)
            self.db.commit()
            return True
        return False
    
    def exists(self, file_id: UUID) -> bool:
        """
        Check if file exists.
        
        Args:
            file_id: File UUID
        
        Returns:
            True if file exists, False otherwise
        """
        return self.db.query(File.id).filter(File.id == file_id).first() is not None
