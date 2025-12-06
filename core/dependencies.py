"""
Dependency injection for FastAPI routes.
Provides repository instances and other dependencies.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from database.models.base import get_db
from database.repositories import FileRepository


def get_file_repository(db: Session = Depends(get_db)) -> FileRepository:
    """
    Dependency to provide FileRepository instance.
    
    Args:
        db: Database session from get_db dependency
    
    Returns:
        FileRepository instance
    
    Usage:
        @router.get("/files")
        async def list_files(file_repo: FileRepository = Depends(get_file_repository)):
            files = file_repo.get_all_paginated()
    """
    return FileRepository(db)
