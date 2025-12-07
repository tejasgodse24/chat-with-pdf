"""
Retrieval endpoints for testing RAG pipeline.
Allows independent testing of vector search before integrating into chat.
"""
from fastapi import APIRouter, HTTPException

from api.schemas.request import RetrieveRequest
from api.schemas.response import RetrieveResponse, RetrievedChunk
from services.vector_service.embeddings_service import generate_embedding
from services.vector_service.upstash_service import query_vectors
from core.utils.logger import setup_logger
from core.exceptions import EmbeddingGenerationError, VectorQueryError

logger = setup_logger(__name__)
retrieval_router = APIRouter(prefix="", tags=["retrieval"])


@retrieval_router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """
    Retrieve relevant chunks from PDF files using semantic search.

    Independent endpoint for testing RAG retrieval pipeline.
    Searches only in specified file_ids using vector similarity.

    Steps:
    1. Generate embedding for query text
    2. Search Upstash Vector with file_id filtering
    3. Return top-k results with similarity scores

    Args:
        request: RetrieveRequest with file_ids, query, and top_k

    Returns:
        RetrieveResponse with retrieved chunks and similarity scores

    Raises:
        HTTPException 400: If embedding generation or vector query fails
        HTTPException 404: If no results found

    Example:
        POST /retrieve
        {
            "file_ids": ["abc-123-uuid"],
            "query": "What is machine learning?",
            "top_k": 5
        }

        Response:
        {
            "query": "What is machine learning?",
            "file_ids": ["abc-123-uuid"],
            "top_k": 5,
            "results": [
                {
                    "chunk_text": "Machine learning is a subset of AI...",
                    "similarity_score": 0.92
                },
                ...
            ],
            "results_count": 5
        }
    """
    logger.info(
        f"Retrieve request: query='{request.query[:50]}...', "
        f"file_ids={len(request.file_ids)}, top_k={request.top_k}"
    )

    try:
        # Step 1: Generate embedding for query
        logger.info("Generating embedding for query")
        query_embedding = generate_embedding(request.query)
        logger.info(f"Generated query embedding: {len(query_embedding)} dimensions")

        # Step 2: Query Upstash Vector with file filtering
        logger.info(f"Querying Upstash Vector: top_k={request.top_k}, file_ids={request.file_ids}")
        results = query_vectors(
            query_vector=query_embedding,
            top_k=request.top_k,
            file_ids=request.file_ids,
            include_metadata=True
        )

        logger.info(f"Query returned {len(results)} results")

        # Step 3: Format results
        retrieved_chunks = []

        for result in results:
            # Extract chunk_text from metadata
            file_id = result.get("metadata", {}).get("file_id", "")
            chunk_id = result.get("metadata", {}).get("chunk_id", "")
            chunk_text = result.get("metadata", {}).get("chunk_text", "")
            similarity_score = result.get("score", 0.0)

            retrieved_chunks.append(
                RetrievedChunk(
                    file_id = file_id,
                    chunk_id = chunk_id,
                    chunk_text=chunk_text,
                    similarity_score=similarity_score
                )
            )

            logger.debug(
                f"Result: score={similarity_score:.3f}, "
                f"text_length={len(chunk_text)}, "
                f"file_id={result.get('metadata', {}).get('file_id')}"
            )

        # Check if any results found
        if not retrieved_chunks:
            logger.warning("No results found for query")
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "No results found for query",
                    "query": request.query,
                    "file_ids": [str(fid) for fid in request.file_ids],
                    "suggestion": "Try a different query or check if files are ingested"
                }
            )

        logger.info(
            f"Retrieval successful: {len(retrieved_chunks)} chunks, "
            f"avg_score={sum(c.similarity_score for c in retrieved_chunks) / len(retrieved_chunks):.3f}"
        )

        return RetrieveResponse(
            # query=request.query,
            # file_ids=request.file_ids,
            # top_k=request.top_k,
            results=retrieved_chunks,
            # results_count=len(retrieved_chunks)
        )

    except EmbeddingGenerationError as e:
        logger.error(f"Failed to generate embedding: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Failed to generate query embedding",
                "error": str(e),
                "suggestion": "Check OpenAI API key and rate limits"
            }
        )

    except VectorQueryError as e:
        logger.error(f"Failed to query vectors: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Failed to query vector database",
                "error": str(e),
                "suggestion": "Check Upstash Vector credentials and namespace"
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error during retrieval: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Unexpected error during retrieval",
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
