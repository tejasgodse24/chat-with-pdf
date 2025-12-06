"""
File management endpoints.
Handles file upload, listing, and retrieval operations.
"""
from fastapi import APIRouter, HTTPException
from uuid import uuid4
from botocore.exceptions import ClientError

from api.schemas.request import PresignRequest
from api.schemas.response import PresignResponse
from core.aws.s3_client import generate_presigned_upload_url
from core.utils.logger import setup_logger

logger = setup_logger(__name__)
files_router = APIRouter(prefix="", tags=["files"])


@files_router.post("/presign", response_model=PresignResponse)
async def generate_presigned_url(request: PresignRequest):
    """
    Generate a presigned S3 URL for file upload.
    
    This endpoint:
    1. Generates a unique file_id (UUID)
    2. Creates S3 key: uploads/{file_id}.pdf
    3. Generates presigned PUT URL (1 hour expiry)
    4. Returns file_id and presigned URL
    
    Note: Database record is NOT created here - the webhook will handle that.
    
    Args:
        request: PresignRequest containing filename
    
    Returns:
        PresignResponse with file_id, presigned_url, and expiry time
    
    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    logger.info(f"Received presign request for filename: {request.filename}")
    
    try:
        # Generate unique file ID
        file_id = uuid4()
        logger.info(f"Generated file_id: {file_id}")
        
        # Create S3 key with uploads/ prefix
        s3_key = f"uploads/{file_id}.pdf"
        
        # Generate presigned URL for upload (1 hour expiry)
        expires_in = 3600  # 1 hour
        presigned_url = generate_presigned_upload_url(s3_key, expires_in)
        
        logger.info(f"Successfully generated presigned URL for file_id: {file_id}")
        
        return PresignResponse(
            file_id=file_id,
            presigned_url=presigned_url,
            expires_in_seconds=expires_in
        )
    
    except ClientError as e:
        # AWS S3 specific errors
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', 'AWS S3 error')
        
        logger.error(
            f"AWS S3 error generating presigned URL: "
            f"Code={error_code}, Message={error_message}"
        )
        
        # Map specific AWS errors to appropriate HTTP status codes
        if error_code == 'NoSuchBucket':
            raise HTTPException(
                status_code=500,
                detail="S3 bucket configuration error. Please contact support."
            )
        elif error_code in ['AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            raise HTTPException(
                status_code=500,
                detail="S3 access denied. Please contact support."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate presigned URL. Please try again."
            )
    
    except ValueError as e:
        # Validation errors (should be caught by Pydantic, but just in case)
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error generating presigned URL: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )
