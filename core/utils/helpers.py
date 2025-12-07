"""
Helper utility functions.
"""
from uuid import UUID
import re
import base64
from core.exceptions import InvalidS3KeyFormatError


def extract_file_id_from_s3_key(s3_key: str) -> UUID:
    """
    Extract file_id (UUID) from S3 key.
    
    Expected format: uploads/{uuid}.pdf
    
    Args:
        s3_key: S3 object key (e.g., "uploads/cacc19ff-21f8-4894-bd24-ca93d8c4de4a.pdf")
    
    Returns:
        UUID extracted from the S3 key
    
    Raises:
        InvalidS3KeyFormatError: If UUID cannot be extracted from S3 key
    """
    # Pattern to match UUID in S3 key
    pattern = r'uploads/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.pdf'
    match = re.match(pattern, s3_key, re.IGNORECASE)
    
    if not match:
        raise InvalidS3KeyFormatError(
            message=f"Invalid S3 key format. Expected: uploads/{{uuid}}.pdf",
            detail={"s3_key": s3_key}
        )
    
    uuid_str = match.group(1)
    return UUID(uuid_str)


def encode_pdf_to_base64(pdf_bytes: bytes) -> str:
    """
    Encode PDF bytes to base64 string.

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        Base64 encoded string

    Example:
        >>> pdf_bytes = b'%PDF-1.4...'
        >>> base64_str = encode_pdf_to_base64(pdf_bytes)
        >>> # Returns: "JVBERi0xLjQK..."
    """
    return base64.b64encode(pdf_bytes).decode('utf-8')