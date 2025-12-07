"""
Upstash Vector service for storing and querying embeddings.
Handles vector storage, retrieval, and metadata filtering for RAG pipeline.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from upstash_vector import Index
from config import get_settings
from core.utils.logger import setup_logger
from core.exceptions import ChatWithPDFException

logger = setup_logger(__name__)
settings = get_settings()


class UpstashVectorError(ChatWithPDFException):
    """Base exception for Upstash Vector operations"""


class VectorUpsertError(UpstashVectorError):
    """Failed to upsert vectors to Upstash"""


class VectorQueryError(UpstashVectorError):
    """Failed to query vectors from Upstash"""


class VectorDeleteError(UpstashVectorError):
    """Failed to delete vectors from Upstash"""


# Initialize Upstash Vector Index
try:
    index = Index(
        url=settings.upstash_vector_url,
        token=settings.upstash_vector_token
    )
    logger.info(
        f"Upstash Vector client initialized: "
        f"namespace='{settings.upstash_vector_namespace}'"
    )
except Exception as e:
    logger.error(f"Failed to initialize Upstash Vector client: {str(e)}")
    index = None


def upsert_vectors(
    vectors: List[Dict[str, Any]],
    namespace: Optional[str] = None
) -> int:
    """
    Upsert (insert or update) vectors to Upstash Vector.

    Each vector should contain:
    - id: Unique identifier for the vector
    - vector: Embedding (list of floats)
    - metadata: Additional data (file_id, chunk_text, etc.)

    Args:
        vectors: List of vector dictionaries to upsert
        namespace: Optional namespace (defaults to config namespace)

    Returns:
        Number of vectors successfully upserted

    Raises:
        VectorUpsertError: If upsert operation fails

    Example:
        >>> vectors = [
        ...     {
        ...         "id": "chunk-uuid-1",
        ...         "vector": [0.123, -0.456, ...],  # 1536 dims
        ...         "metadata": {
        ...             "file_id": "file-uuid",
        ...             "chunk_id": "chunk-uuid-1",
        ...             "chunk_index": 0,
        ...             "chunk_text": "Machine learning is..."
        ...         }
        ...     },
        ...     ...
        ... ]
        >>> count = upsert_vectors(vectors)
        >>> print(f"Upserted {count} vectors")
    """
    if not index:
        raise VectorUpsertError(
            message="Upstash Vector client not initialized",
            detail={"vectors_count": len(vectors)}
        )

    if not vectors:
        logger.warning("No vectors provided for upsert")
        return 0

    # Use namespace from config if not provided
    ns = namespace or settings.upstash_vector_namespace

    logger.info(f"Upserting {len(vectors)} vectors to namespace '{ns}'")

    try:
        # Prepare vectors for Upstash format
        # Upstash expects: [(id, vector, metadata), ...]
        upstash_vectors = []

        for vec in vectors:
            vector_id = str(vec.get("id"))
            vector_data = vec.get("vector")
            metadata = vec.get("metadata", {})

            if not vector_id or not vector_data:
                logger.warning(f"Skipping invalid vector: missing id or vector data")
                continue

            upstash_vectors.append((vector_id, vector_data, metadata))

        if not upstash_vectors:
            logger.warning("No valid vectors after filtering")
            return 0

        # Upsert to Upstash with namespace
        index.upsert(
            vectors=upstash_vectors,
            namespace=ns
        )

        logger.info(
            f"Successfully upserted {len(upstash_vectors)} vectors to namespace '{ns}'"
        )

        return len(upstash_vectors)

    except Exception as e:
        logger.error(f"Error upserting vectors: {str(e)}")
        raise VectorUpsertError(
            message=f"Failed to upsert vectors: {str(e)}",
            detail={
                "vectors_count": len(vectors),
                "namespace": ns,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


def query_vectors(
    query_vector: List[float],
    top_k: int = 5,
    file_ids: Optional[List[UUID]] = None,
    namespace: Optional[str] = None,
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Query Upstash Vector for similar vectors.

    Uses cosine similarity to find most similar vectors.
    Supports metadata filtering by file_ids.

    Args:
        query_vector: Query embedding (1536 dimensions)
        top_k: Number of top results to return (default: 5)
        file_ids: Optional list of file UUIDs to filter by
        namespace: Optional namespace (defaults to config namespace)
        include_metadata: Whether to include metadata in results (default: True)

    Returns:
        List of result dictionaries:
        [
            {
                "id": "chunk-uuid-1",
                "score": 0.92,  # Cosine similarity (0-1)
                "metadata": {
                    "file_id": "file-uuid",
                    "chunk_text": "...",
                    ...
                }
            },
            ...
        ]

    Raises:
        VectorQueryError: If query operation fails

    Example:
        >>> # Query with file filtering
        >>> results = query_vectors(
        ...     query_vector=[0.123, -0.456, ...],
        ...     top_k=5,
        ...     file_ids=["file-uuid-1", "file-uuid-2"]
        ... )
        >>> for result in results:
        ...     print(f"Score: {result['score']:.3f}")
        ...     print(f"Text: {result['metadata']['chunk_text'][:50]}")
    """
    if not index:
        raise VectorQueryError(
            message="Upstash Vector client not initialized",
            detail={"top_k": top_k}
        )

    if not query_vector:
        raise VectorQueryError(
            message="Query vector is empty",
            detail={"top_k": top_k}
        )

    # Use namespace from config if not provided
    ns = namespace or settings.upstash_vector_namespace

    logger.info(
        f"Querying vectors: top_k={top_k}, "
        f"file_ids={len(file_ids) if file_ids else 'all'}, "
        f"namespace='{ns}'"
    )

    try:
        # Build metadata filter if file_ids provided
        # Upstash Vector Python SDK expects filter as string expression
        metadata_filter = None
        if file_ids:
            # Convert UUIDs to strings for metadata filter
            file_id_strings = [str(fid) for fid in file_ids]

            # Build filter string based on number of file_ids
            if len(file_id_strings) == 1:
                # Single file: file_id = 'uuid'
                metadata_filter = f"file_id = '{file_id_strings[0]}'"
            else:
                # Multiple files: file_id IN ('uuid1', 'uuid2', ...)
                file_ids_quoted = "', '".join(file_id_strings)
                metadata_filter = f"file_id IN ('{file_ids_quoted}')"

            logger.debug(f"Using metadata filter: {metadata_filter}")

        # Query Upstash Vector
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            filter=metadata_filter,
            include_metadata=include_metadata,
            namespace=ns
        )

        # Format results
        formatted_results = []

        for result in results:
            formatted_result = {
                "id": result.id,
                "score": result.score,
            }

            if include_metadata and hasattr(result, 'metadata'):
                formatted_result["metadata"] = result.metadata
            else:
                formatted_result["metadata"] = {}

            formatted_results.append(formatted_result)

        logger.info(
            f"Query returned {len(formatted_results)} results "
            f"(avg_score={sum(r['score'] for r in formatted_results) / len(formatted_results):.3f})"
            if formatted_results else "Query returned 0 results"
        )

        return formatted_results

    except Exception as e:
        logger.error(f"Error querying vectors: {str(e)}")
        raise VectorQueryError(
            message=f"Failed to query vectors: {str(e)}",
            detail={
                "top_k": top_k,
                "file_ids_count": len(file_ids) if file_ids else 0,
                "namespace": ns,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


def delete_vectors_by_file_id(
    file_id: UUID,
    namespace: Optional[str] = None
) -> int:
    """
    Delete all vectors associated with a specific file_id.

    Useful for cleanup when a file is deleted or re-ingested.

    Args:
        file_id: File UUID to delete vectors for
        namespace: Optional namespace (defaults to config namespace)

    Returns:
        Number of vectors deleted (approximation)

    Raises:
        VectorDeleteError: If delete operation fails

    Example:
        >>> deleted = delete_vectors_by_file_id("file-uuid-123")
        >>> print(f"Deleted {deleted} vectors")
    """
    if not index:
        raise VectorDeleteError(
            message="Upstash Vector client not initialized",
            detail={"file_id": str(file_id)}
        )

    # Use namespace from config if not provided
    ns = namespace or settings.upstash_vector_namespace

    logger.info(f"Deleting vectors for file_id={file_id} in namespace '{ns}'")

    try:
        # Note: Upstash Vector doesn't have a direct "delete by metadata" method
        # We need to query first, then delete by IDs

        # Query all vectors for this file (high top_k to get all)
        results = index.query(
            vector=[0.0] * 1536,  # Dummy vector (not used for metadata-only query)
            top_k=10000,  # High limit to get all chunks for this file
            filter={"file_id": str(file_id)},
            include_metadata=False,  # Don't need metadata for deletion
            namespace=ns
        )

        if not results:
            logger.info(f"No vectors found for file_id={file_id}")
            return 0

        # Extract IDs
        vector_ids = [result.id for result in results]

        # Delete by IDs
        index.delete(
            ids=vector_ids,
            namespace=ns
        )

        logger.info(f"Deleted {len(vector_ids)} vectors for file_id={file_id}")

        return len(vector_ids)

    except Exception as e:
        logger.error(f"Error deleting vectors: {str(e)}")
        raise VectorDeleteError(
            message=f"Failed to delete vectors: {str(e)}",
            detail={
                "file_id": str(file_id),
                "namespace": ns,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


def get_vector_info(namespace: Optional[str] = None) -> Dict[str, Any]:
    """
    Get information about the Upstash Vector index.

    Useful for debugging and monitoring.

    Args:
        namespace: Optional namespace (defaults to config namespace)

    Returns:
        Dictionary with index information

    Example:
        >>> info = get_vector_info()
        >>> print(f"Total vectors: {info.get('vector_count', 'unknown')}")
    """
    if not index:
        logger.warning("Upstash Vector client not initialized")
        return {"error": "Client not initialized"}

    # Use namespace from config if not provided
    ns = namespace or settings.upstash_vector_namespace

    try:
        # Get index info (Upstash provides index.info() method)
        info = index.info()

        logger.info(f"Retrieved index info for namespace '{ns}': {info}")

        return {
            "namespace": ns,
            "info": info
        }

    except Exception as e:
        logger.error(f"Error getting index info: {str(e)}")
        return {
            "namespace": ns,
            "error": str(e)
        }
