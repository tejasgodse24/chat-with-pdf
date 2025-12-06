"""
Request Pydantic models for API endpoints.
"""
from pydantic import BaseModel, Field, field_validator


class PresignRequest(BaseModel):
    """Request model for presigned URL generation"""
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the PDF file to upload (must be a .pdf file)",
        example="document.pdf"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_pdf_extension(cls, v: str) -> str:
        """Validate that filename has .pdf extension"""
        if not v.lower().endswith('.pdf'):
            raise ValueError('Only PDF files are allowed. Filename must end with .pdf')
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(char in v for char in invalid_chars):
            raise ValueError(f'Filename contains invalid characters: {invalid_chars}')
        
        return v
