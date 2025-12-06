"""
Centralized exception handlers for FastAPI application.
Maps custom exceptions to HTTP responses.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from core.utils.logger import setup_logger
from core.exceptions import (
    S3BucketNotFoundError,
    S3AccessDeniedError,
    S3KeyNotFoundError,
    S3UploadError,
    S3DownloadError,
    FileRecordNotFoundError,
    DatabaseConnectionError,
    InvalidFileFormatError,
    InvalidS3KeyFormatError,
)

logger = setup_logger(__name__)


def register_exception_handlers(app: FastAPI):
    """
    Register all exception handlers with the FastAPI app.
    
    Call this once in main.py after creating the app instance.
    
    Args:
        app: FastAPI application instance
    """
    
    # ========================================================================
    # S3 / Storage Exceptions
    # ========================================================================
    
    @app.exception_handler(S3BucketNotFoundError)
    async def s3_bucket_not_found_handler(request: Request, exc: S3BucketNotFoundError):
        """Handle S3 bucket not found errors (500 - our configuration issue)"""
        logger.error(f"S3 bucket not found: {exc.message}", extra={"detail": exc.detail})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "S3BucketNotFoundError",
                "message": "S3 bucket configuration error. Please contact support.",
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(S3AccessDeniedError)
    async def s3_access_denied_handler(request: Request, exc: S3AccessDeniedError):
        """Handle S3 access denied errors (500 - our credentials issue)"""
        logger.error(f"S3 access denied: {exc.message}", extra={"detail": exc.detail})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "S3AccessDeniedError",
                "message": "S3 access denied. Please contact support.",
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(S3KeyNotFoundError)
    async def s3_key_not_found_handler(request: Request, exc: S3KeyNotFoundError):
        """Handle S3 key not found errors (404 - file doesn't exist)"""
        logger.warning(f"S3 key not found: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "S3KeyNotFoundError",
                "message": "File not found in S3.",
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(S3UploadError)
    async def s3_upload_error_handler(request: Request, exc: S3UploadError):
        """Handle S3 upload errors (500 - S3 operation failed)"""
        logger.error(f"S3 upload failed: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "S3UploadError",
                "message": "S3 upload operation failed. Please try again.",
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(S3DownloadError)
    async def s3_download_error_handler(request: Request, exc: S3DownloadError):
        """Handle S3 download errors (500 - S3 operation failed)"""
        logger.error(f"S3 download failed: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "S3DownloadError",
                "message": "S3 download operation failed. Please try again.",
                "detail": exc.detail
            }
        )
    
    # ========================================================================
    # Database Exceptions
    # ========================================================================
    
    @app.exception_handler(FileRecordNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileRecordNotFoundError):
        """Handle file record not found errors (404)"""
        logger.warning(f"File record not found: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "FileRecordNotFoundError",
                "message": "File not found.",
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_handler(request: Request, exc: DatabaseConnectionError):
        """Handle database connection errors (503 - service unavailable)"""
        logger.critical(f"Database connection failed: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "DatabaseConnectionError",
                "message": "Database service unavailable. Please try again later.",
                "detail": {}
            }
        )
    
    # ========================================================================
    # Validation Exceptions
    # ========================================================================
    
    @app.exception_handler(InvalidFileFormatError)
    async def invalid_file_format_handler(request: Request, exc: InvalidFileFormatError):
        """Handle invalid file format errors (400 - client error)"""
        logger.warning(f"Invalid file format: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "InvalidFileFormatError",
                "message": str(exc.message),
                "detail": exc.detail
            }
        )
    
    @app.exception_handler(InvalidS3KeyFormatError)
    async def invalid_s3_key_handler(request: Request, exc: InvalidS3KeyFormatError):
        """Handle invalid S3 key format errors (400 - client error)"""
        logger.warning(f"Invalid S3 key format: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "InvalidS3KeyFormatError",
                "message": str(exc.message),
                "detail": exc.detail
            }
        )
    
    # ========================================================================
    # FastAPI Built-in Exceptions
    # ========================================================================
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors (422)"""
        errors = exc.errors()
        logger.warning(f"Request validation error: {errors}")
        
        # Convert errors to JSON-serializable format
        error_details = []
        for error in errors:
            error_details.append({
                "loc": error.get("loc", []),
                "msg": error.get("msg", ""),
                "type": error.get("type", "")
            })
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "Invalid request data.",
                "detail": error_details
            }
        )
    
    # ========================================================================
    # Catch-All Handler (Must be last!)
    # ========================================================================
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions (500)"""
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
                "detail": {}
            }
        )
