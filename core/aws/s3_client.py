"""
S3 client for AWS operations.
Handles presigned URL generation for upload and download.
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from config import get_settings
from core.utils.logger import setup_logger
from core.exceptions import (
    S3BucketNotFoundError,
    S3AccessDeniedError,
    S3KeyNotFoundError,
    S3UploadError,
    S3DownloadError
)

logger = setup_logger(__name__)
settings = get_settings()

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)


def generate_presigned_upload_url(s3_key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for uploading a file to S3.
    
    Args:
        s3_key: The S3 object key (path) for the file
        expires_in: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL string for PUT operation
    
    Raises:
        S3BucketNotFoundError: If S3 bucket doesn't exist
        S3AccessDeniedError: If S3 access is denied
        S3UploadError: For other S3 errors
    """
    try:
        logger.info(f"Generating presigned upload URL for S3 key: {s3_key}")
        
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.s3_bucket_name,
                'Key': s3_key,
                'ContentType': 'application/pdf'
            },
            ExpiresIn=expires_in
        )
        
        logger.info(f"Successfully generated presigned upload URL")
        return url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        # Translate AWS errors to custom exceptions
        if error_code == 'NoSuchBucket':
            raise S3BucketNotFoundError(
                message=f"S3 bucket not found: {settings.s3_bucket_name}",
                detail={"bucket": settings.s3_bucket_name, "error_code": error_code}
            )
        elif error_code in ['AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            raise S3AccessDeniedError(
                message=f"S3 access denied",
                detail={"bucket": settings.s3_bucket_name, "error_code": error_code}
            )
        else:
            raise S3UploadError(
                message=f"S3 upload error: {error_message}",
                detail={"s3_key": s3_key, "error_code": error_code}
            )
            
    except BotoCoreError as e:
        raise S3UploadError(
            message=f"AWS service error: {str(e)}",
            detail={"s3_key": s3_key}
        )


def generate_presigned_download_url(s3_key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for downloading a file from S3.
    
    Args:
        s3_key: The S3 object key (path) for the file
        expires_in: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL string for GET operation
    
    Raises:
        S3KeyNotFoundError: If S3 key doesn't exist
        S3AccessDeniedError: If S3 access is denied
        S3DownloadError: For other S3 errors
    """
    try:
        logger.info(f"Generating presigned download URL for S3 key: {s3_key}")
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.s3_bucket_name,
                'Key': s3_key
            },
            ExpiresIn=expires_in
        )
        
        logger.info(f"Successfully generated presigned download URL")
        return url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        # Translate AWS errors to custom exceptions
        if error_code == 'NoSuchKey':
            raise S3KeyNotFoundError(
                message=f"S3 key not found: {s3_key}",
                detail={"s3_key": s3_key, "error_code": error_code}
            )
        elif error_code in ['AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            raise S3AccessDeniedError(
                message=f"S3 access denied",
                detail={"bucket": settings.s3_bucket_name, "error_code": error_code}
            )
        else:
            raise S3DownloadError(
                message=f"S3 download error: {error_message}",
                detail={"s3_key": s3_key, "error_code": error_code}
            )
            
    except BotoCoreError as e:
        raise S3DownloadError(
            message=f"AWS service error: {str(e)}",
            detail={"s3_key": s3_key}
        )
