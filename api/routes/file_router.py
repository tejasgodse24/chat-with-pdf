"""
File management endpoints.
Handles file upload, listing, and retrieval operations.
"""
from fastapi import APIRouter, Depends, Query
from uuid import uuid4, UUID

from api.schemas.request import PresignRequest
from api.schemas.response import PresignResponse, FileListResponse, FileResponse, FileDetailResponse
from core.aws.s3_client import generate_presigned_upload_url, generate_presigned_download_url
from core.exceptions import FileRecordNotFoundError
from core.utils.logger import setup_logger
from core.dependencies import get_file_repository
from database.repositories import FileRepository

logger = setup_logger(__name__)
files_router = APIRouter(prefix="", tags=["files"])


@files_router.post("/presign", response_model=PresignResponse)
async def generate_presigned_url(request: PresignRequest):
    """
    Generate a presigned S3 URL for file upload.
    
    Args:
        request: PresignRequest containing filename
    
    Returns:
        PresignResponse with file_id, presigned_url, and expiry time
    
    Raises:
        S3BucketNotFoundError: If S3 bucket doesn't exist
        S3AccessDeniedError: If S3 access is denied
        S3UploadError: For other S3 errors
    """
    logger.info(f"Received presign request for filename: {request.filename}")
    
    # Generate unique file ID
    file_id = uuid4()
    
    # Create S3 key with uploads/ prefix
    s3_key = f"uploads/{file_id}.pdf"
    
    # Generate presigned URL for upload (1 hour expiry)
    # Exceptions are handled by global exception handlers
    expires_in = 3600  # 1 hour
    presigned_url = generate_presigned_upload_url(s3_key, expires_in)
    
    logger.info(f"Successfully generated presigned URL for file_id: {file_id}")
    
    return PresignResponse(
        file_id=file_id,
        presigned_url=presigned_url,
        expires_in_seconds=expires_in
    )


@files_router.get("/files", response_model=FileListResponse)
async def list_files(
    limit: int = Query(20, ge=1, le=100, description="Number of files to return"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    file_repo: FileRepository = Depends(get_file_repository)
):
    """
    List all uploaded files with pagination.
    
    Args:
        limit: Maximum number of files to return (1-100, default: 20)
        offset: Number of files to skip for pagination (default: 0)
        file_repo: FileRepository instance (injected)
    
    Returns:
        FileListResponse with paginated file list and metadata
    
    Raises:
        DatabaseConnectionError: If database query fails
    """
    logger.info(f"Fetching files list: limit={limit}, offset={offset}")
    
    # Get total count using repository
    total = file_repo.count_all()
    
    # Get paginated files using repository
    files = file_repo.get_all_paginated(limit=limit, offset=offset)
    
    # Convert ORM models to response models
    file_responses = [
        FileResponse(
            file_id=file.id,
            s3_key=file.s3_key,
            ingestion_status=file.ingestion_status.value,
            created_at=file.created_at,
            updated_at=file.updated_at
        )
        for file in files
    ]
    
    logger.info(f"Successfully fetched {len(file_responses)} files (total: {total})")
    
    return FileListResponse(
        files=file_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@files_router.get("/files/{file_id}", response_model=FileDetailResponse)
async def get_file_detail(
    file_id: UUID,
    file_repo: FileRepository = Depends(get_file_repository)
):
    """
    Get specific file details with presigned download URL.
    
    Args:
        file_id: UUID of the file to retrieve
        file_repo: FileRepository instance (injected)
    
    Returns:
        FileDetailResponse with file details and presigned download URL
    
    Raises:
        FileRecordNotFoundError: If file doesn't exist in database (404)
        S3KeyNotFoundError: If file doesn't exist in S3 (404)
        S3DownloadError: For other S3 errors (500)
    """
    logger.info(f"Fetching file detail for file_id: {file_id}")
    
    # Get file from database using repository
    db_file = file_repo.get_by_id(file_id)
    
    # If file not found, raise exception (handled by global exception handler)
    if not db_file:
        raise FileRecordNotFoundError(
            message=f"File not found: {file_id}",
            detail={"file_id": str(file_id)}
        )
    
    # Generate presigned download URL (1 hour expiry)
    # S3 exceptions handled by global exception handlers
    expires_in = 3600  # 1 hour
    presigned_download_url = generate_presigned_download_url(db_file.s3_key, expires_in)
    
    logger.info(f"Successfully generated download URL for file_id: {file_id}")
    
    return FileDetailResponse(
        file_id=db_file.id,
        s3_key=db_file.s3_key,
        ingestion_status=db_file.ingestion_status.value,
        presigned_download_url=presigned_download_url,
        download_url_expires_in_seconds=expires_in,
        created_at=db_file.created_at,
        updated_at=db_file.updated_at
    )
