"""
Custom exceptions for Chat with PDF application.
All exceptions inherit from base ChatWithPDFException.
"""


# ============================================================================
# Base Exception
# ============================================================================

class ChatWithPDFException(Exception):
    """Base exception for all application errors"""
    def __init__(self, message: str, detail: dict = None):
        self.message = message
        self.detail = detail or {}
        super().__init__(self.message)


# ============================================================================
# S3 / Storage Exceptions
# ============================================================================

class S3Exception(ChatWithPDFException):
    """Base exception for S3-related errors"""


class S3BucketNotFoundError(S3Exception):
    """S3 bucket doesn't exist or not accessible"""


class S3AccessDeniedError(S3Exception):
    """S3 access denied (credentials/permissions issue)"""


class S3KeyNotFoundError(S3Exception):
    """S3 object key doesn't exist"""


class S3UploadError(S3Exception):
    """Failed to generate presigned upload URL"""


class S3DownloadError(S3Exception):
    """Failed to generate presigned download URL"""


# ============================================================================
# Database Exceptions
# ============================================================================

class DatabaseException(ChatWithPDFException):
    """Base exception for database errors"""


class FileRecordNotFoundError(DatabaseException):
    """File record not found in database"""


class DatabaseConnectionError(DatabaseException):
    """Database connection failed"""


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationException(ChatWithPDFException):
    """Base exception for validation errors"""


class InvalidFileFormatError(ValidationException):
    """Invalid file format (not PDF)"""


class InvalidS3KeyFormatError(ValidationException):
    """Invalid S3 key format (cannot extract UUID)"""
