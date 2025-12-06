"""
S3 client for AWS operations.
Handles presigned URL generation for upload and download.
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from config import get_settings
from core.utils.logger import setup_logger

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
        ClientError: If AWS S3 operation fails
        Exception: For other unexpected errors
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
        
        logger.info(f"Successfully generated presigned upload URL for: {s3_key}")
        return url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"AWS ClientError generating presigned upload URL: "
            f"Code={error_code}, Message={error_message}, Key={s3_key}"
        )
        
        # Re-raise with preserved error information
        raise
        
    except BotoCoreError as e:
        logger.error(f"BotoCoreError generating presigned upload URL: {str(e)}")
        raise Exception(f"AWS service error: {str(e)}")
        
    except Exception as e:
        logger.error(
            f"Unexpected error generating presigned upload URL: {str(e)}",
            exc_info=True
        )
        raise


def generate_presigned_download_url(s3_key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for downloading a file from S3.
    
    Args:
        s3_key: The S3 object key (path) for the file
        expires_in: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL string for GET operation
    
    Raises:
        ClientError: If AWS S3 operation fails
        Exception: For other unexpected errors
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
        
        logger.info(f"Successfully generated presigned download URL for: {s3_key}")
        return url
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"AWS ClientError generating presigned download URL: "
            f"Code={error_code}, Message={error_message}, Key={s3_key}"
        )
        
        # Re-raise with preserved error information
        raise
        
    except BotoCoreError as e:
        logger.error(f"BotoCoreError generating presigned download URL: {str(e)}")
        raise Exception(f"AWS service error: {str(e)}")
        
    except Exception as e:
        logger.error(
            f"Unexpected error generating presigned download URL: {str(e)}",
            exc_info=True
        )
        raise
