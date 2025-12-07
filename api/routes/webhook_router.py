"""
Webhook endpoints for S3 event notifications.
Handles file ingestion notifications from AWS Lambda with full RAG pipeline.
"""
from fastapi import APIRouter, Depends
from uuid import uuid4

from api.schemas.request import WebhookIngestRequest
from core.utils.helpers import extract_file_id_from_s3_key
from core.dependencies import get_file_repository
from database.repositories import FileRepository
from database.models.file import IngestionStatus
from core.utils.logger import setup_logger

# Import ingestion pipeline services
from services.file_service.s3_service import download_pdf_from_s3
from services.file_service.pdf_extraction_service import extract_text_from_pdf
from services.file_service.chunking_service import chunk_pdf_text
from services.vector_service.embeddings_service import generate_embeddings_batch
from services.vector_service.upstash_service import upsert_vectors

# Import exceptions
from core.exceptions import (
    PDFExtractionError,
    EmbeddingGenerationError,
    VectorUpsertError,
    S3DownloadError
)

logger = setup_logger(__name__)
webhook_router = APIRouter(prefix="/webhook", tags=["webhooks"])


@webhook_router.post("/ingest")
async def webhook_ingest(
    request: WebhookIngestRequest,
    file_repo: FileRepository = Depends(get_file_repository)
):
    """
    Webhook endpoint for S3 upload notifications with full ingestion pipeline.

    Called by AWS Lambda when a file is uploaded to S3.

    Full Pipeline:
    1. Create database record with status "uploaded"
    2. Download PDF from S3
    3. Extract text from PDF
    4. Chunk text (512 tokens, 20% overlap)
    5. Generate embeddings (OpenAI text-embedding-3-small)
    6. Store vectors in Upstash with metadata
    7. Update status to "completed"

    If any step fails, status is set to "failed" with error message.

    Args:
        request: WebhookIngestRequest containing s3_bucket and s3_key
        file_repo: FileRepository instance (injected)

    Returns:
        Success response with file_id, status, and processing summary

    Raises:
        InvalidS3KeyFormatError: If S3 key format is invalid
    """
    logger.info(
        f"Received webhook ingest notification: "
        f"bucket={request.s3_bucket}, key={request.s3_key}"
    )

    # Extract file_id from S3 key
    file_id = extract_file_id_from_s3_key(request.s3_key)
    logger.info(f"Extracted file_id: {file_id} from S3 key: {request.s3_key}")

    # Check if file already exists
    existing_file = file_repo.get_by_id(file_id)
    if existing_file:
        logger.warning(f"File {file_id} already exists with status {existing_file.ingestion_status.value}")
        return {
            "status": "success",
            "message": "File already exists",
            "file_id": str(file_id),
            "ingestion_status": existing_file.ingestion_status.value
        }

    # Step 1: Create file record with status "uploaded"
    db_file = file_repo.create(
        file_id=file_id,
        s3_key=request.s3_key,
        ingestion_status=IngestionStatus.UPLOADED
    )

    logger.info(
        f"Created file record: id={file_id}, s3_key={request.s3_key}, "
        f"status={db_file.ingestion_status.value}"
    )

    # Start ingestion pipeline
    try:
        # Step 2: Download PDF from S3
        logger.info(f"[Step 2/6] Downloading PDF from S3: {request.s3_key}")
        pdf_bytes = download_pdf_from_s3(request.s3_key)
        logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")

        # Step 3: Extract text from PDF
        logger.info(f"[Step 3/6] Extracting text from PDF")
        pdf_text = extract_text_from_pdf(pdf_bytes)
        logger.info(f"Extracted text: {len(pdf_text)} characters")

        # Step 4: Chunk text
        logger.info(f"[Step 4/6] Chunking text (512 tokens, 20% overlap)")
        chunks = chunk_pdf_text(pdf_text)
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            raise PDFExtractionError(
                message="No chunks created from PDF text",
                detail={"file_id": str(file_id), "text_length": len(pdf_text)}
            )

        # Step 5: Generate embeddings
        logger.info(f"[Step 5/6] Generating embeddings for {len(chunks)} chunks")
        chunk_texts = [chunk["chunk_text"] for chunk in chunks]
        embeddings = generate_embeddings_batch(chunk_texts)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Step 6: Prepare vectors for Upstash
        logger.info(f"[Step 6/6] Preparing and upserting vectors to Upstash")
        vectors = []

        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid4())

            vectors.append({
                "id": chunk_id,
                "vector": embeddings[i],
                "metadata": {
                    "file_id": str(file_id),
                    "chunk_id": chunk_id,
                    "chunk_index": chunk["chunk_index"],
                    "chunk_text": chunk["chunk_text"]
                }
            })

        # Upsert vectors to Upstash
        upserted_count = upsert_vectors(vectors)
        logger.info(f"Successfully upserted {upserted_count} vectors to Upstash")

        # Step 7: Update status to "completed"
        file_repo.update_status(file_id, IngestionStatus.COMPLETED)
        logger.info(f"Ingestion completed successfully for file {file_id}")

        return {
            "status": "success",
            "message": "File ingestion completed successfully",
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.COMPLETED.value,
            "summary": {
                "pdf_size_bytes": len(pdf_bytes),
                "text_chars": len(pdf_text),
                "chunks_created": len(chunks),
                "vectors_stored": upserted_count
            }
        }

    except S3DownloadError as e:
        # S3 download failed
        error_msg = f"Failed to download PDF from S3: {str(e)}"
        logger.error(error_msg)
        file_repo.update_status(
            file_id,
            IngestionStatus.FAILED,
            error_message=error_msg
        )

        return {
            "status": "failed",
            "message": error_msg,
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.FAILED.value,
            "error": str(e)
        }

    except PDFExtractionError as e:
        # PDF extraction failed (corrupted PDF or scanned PDF)
        error_msg = f"Failed to extract text from PDF: {str(e)}"
        logger.error(error_msg)
        file_repo.update_status(
            file_id,
            IngestionStatus.FAILED,
            error_message=error_msg
        )

        return {
            "status": "failed",
            "message": error_msg,
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.FAILED.value,
            "error": str(e),
            "suggestion": "This may be a scanned PDF requiring OCR"
        }

    except EmbeddingGenerationError as e:
        # OpenAI embedding generation failed
        error_msg = f"Failed to generate embeddings: {str(e)}"
        logger.error(error_msg)
        file_repo.update_status(
            file_id,
            IngestionStatus.FAILED,
            error_message=error_msg
        )

        return {
            "status": "failed",
            "message": error_msg,
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.FAILED.value,
            "error": str(e),
            "suggestion": "Check OpenAI API key and rate limits"
        }

    except VectorUpsertError as e:
        # Upstash upsert failed
        error_msg = f"Failed to store vectors in Upstash: {str(e)}"
        logger.error(error_msg)
        file_repo.update_status(
            file_id,
            IngestionStatus.FAILED,
            error_message=error_msg
        )

        return {
            "status": "failed",
            "message": error_msg,
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.FAILED.value,
            "error": str(e),
            "suggestion": "Check Upstash Vector credentials and namespace"
        }

    except Exception as e:
        # Unexpected error
        error_msg = f"Unexpected error during ingestion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        file_repo.update_status(
            file_id,
            IngestionStatus.FAILED,
            error_message=error_msg
        )

        return {
            "status": "failed",
            "message": error_msg,
            "file_id": str(file_id),
            "ingestion_status": IngestionStatus.FAILED.value,
            "error": str(e),
            "error_type": type(e).__name__
        }
