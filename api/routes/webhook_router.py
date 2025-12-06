"""
Webhook endpoints for S3 event notifications.
Handles file ingestion notifications from AWS Lambda.
"""
from fastapi import APIRouter, Depends

from api.schemas.request import WebhookIngestRequest
from core.utils.helpers import extract_file_id_from_s3_key
from core.dependencies import get_file_repository
from database.repositories import FileRepository
from database.models.file import IngestionStatus
from core.utils.logger import setup_logger

logger = setup_logger(__name__)
webhook_router = APIRouter(prefix="/webhook", tags=["webhooks"])

@webhook_router.post("/ingest")
async def webhook_ingest(
    request: WebhookIngestRequest,
    file_repo: FileRepository = Depends(get_file_repository)
):
    """
    Webhook endpoint for S3 upload notifications.
    
    Called by AWS Lambda when a file is uploaded to S3.
    Creates a database record for the uploaded file.
    
    Args:
        request: WebhookIngestRequest containing s3_bucket and s3_key
        file_repo: FileRepository instance (injected)
    
    Returns:
        Success response with file_id and status
    
    Raises:
        InvalidS3KeyFormatError: If S3 key format is invalid
        DatabaseConnectionError: If database operation fails
    """
    logger.info(
        f"Received webhook ingest notification: "
        f"bucket={request.s3_bucket}, key={request.s3_key}"
    )
    
    # Extract file_id from S3 key
    # InvalidS3KeyFormatError handled by global exception handler
    file_id = extract_file_id_from_s3_key(request.s3_key)
    logger.info(f"Extracted file_id: {file_id} from S3 key: {request.s3_key}")
    
    # Check if file already exists using repository
    existing_file = file_repo.get_by_id(file_id)
    if existing_file:
        logger.warning(f"File {file_id} already exists in database. Skipping creation.")
        return {
            "status": "success",
            "message": "File already exists",
            "file_id": str(file_id),
            "ingestion_status": existing_file.ingestion_status.value
        }
    
    # Create new file record using repository
    db_file = file_repo.create(
        file_id=file_id,
        s3_key=request.s3_key,
        ingestion_status=IngestionStatus.UPLOADED
    )
    
    logger.info(
        f"Successfully created file record: "
        f"id={file_id}, s3_key={request.s3_key}, status={db_file.ingestion_status.value}"
    )
    
    return {
        "status": "success",
        "message": "File record created successfully",
        "file_id": str(file_id),
        "ingestion_status": db_file.ingestion_status.value
    }
