"""
PDF text extraction service using PyMuPDF.
Handles PDF text extraction with error handling and quality checks.
"""
from typing import Optional
from core.utils.logger import setup_logger
from core.exceptions import PDFExtractionError

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError(
        "PyMuPDF is required for PDF extraction. Install with: pip install pymupdf"
    )

logger = setup_logger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes using PyMuPDF.

    Uses PyMuPDF (fitz) for fast and reliable text extraction.
    Handles multi-page PDFs and concatenates all text.

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        Extracted text from all pages concatenated

    Raises:
        PDFExtractionError: If PDF cannot be opened or text extraction fails

    Example:
        >>> from services.file_service.s3_service import download_pdf_from_s3
        >>> pdf_bytes = download_pdf_from_s3("uploads/abc-123.pdf")
        >>> text = extract_text_from_pdf(pdf_bytes)
        >>> print(f"Extracted {len(text)} characters")
    """
    logger.info(f"Extracting text from PDF ({len(pdf_bytes)} bytes)")

    try:
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        page_count = doc.page_count
        logger.info(f"PDF opened: {page_count} pages")

        # Extract text from all pages
        full_text = ""
        empty_pages = 0

        for page_num in range(page_count):
            page = doc[page_num]
            page_text = page.get_text()

            if not page_text.strip():
                empty_pages += 1
                logger.debug(f"Page {page_num + 1} has no text (possibly image/scanned)")
            else:
                full_text += page_text
                # Add page separator (optional, helps maintain structure)
                full_text += "\n\n"

            logger.debug(
                f"Page {page_num + 1}/{page_count}: "
                f"extracted {len(page_text)} characters"
            )

        # Close the document
        doc.close()

        # Log extraction summary
        total_chars = len(full_text)
        logger.info(
            f"Text extraction complete: {total_chars} characters, "
            f"{empty_pages}/{page_count} empty pages"
        )

        # Check if we got any text
        if not full_text.strip():
            logger.warning(
                "No text extracted from PDF. This may be a scanned PDF (images only). "
                "OCR would be needed for text extraction."
            )
            raise PDFExtractionError(
                message="No text found in PDF. This may be a scanned PDF requiring OCR.",
                detail={
                    "page_count": page_count,
                    "empty_pages": empty_pages,
                    "suggestion": "Use OCR (pytesseract) for scanned PDFs"
                }
            )

        return full_text

    except fitz.FileDataError as e:
        logger.error(f"Invalid PDF file: {str(e)}")
        raise PDFExtractionError(
            message="Invalid or corrupted PDF file",
            detail={"error": str(e), "pdf_size": len(pdf_bytes)}
        )

    except fitz.EmptyFileError as e:
        logger.error(f"Empty PDF file: {str(e)}")
        raise PDFExtractionError(
            message="PDF file is empty",
            detail={"error": str(e), "pdf_size": len(pdf_bytes)}
        )

    except Exception as e:
        logger.error(f"Unexpected error during PDF extraction: {str(e)}")
        raise PDFExtractionError(
            message=f"Failed to extract text from PDF: {str(e)}",
            detail={"error": str(e), "error_type": type(e).__name__}
        )

