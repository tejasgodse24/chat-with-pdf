"""
OpenAI embeddings service for generating vector embeddings.
Handles text-to-vector conversion using OpenAI's text-embedding-3-small model.
"""
import time
from typing import List
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from config import get_settings
from core.utils.logger import setup_logger
from core.exceptions import ChatWithPDFException

logger = setup_logger(__name__)
settings = get_settings()

# OpenAI embeddings configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # Output dimension for text-embedding-3-small
MAX_RETRIES = 3
RETRY_DELAY = 1  # Initial delay in seconds (exponential backoff)


class EmbeddingGenerationError(ChatWithPDFException):
    """Failed to generate embeddings from OpenAI"""


# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding vector for a single text input.

    Uses OpenAI's text-embedding-3-small model to convert text into
    a 1536-dimensional vector representation.

    Args:
        text: Input text to embed (max 8191 tokens)

    Returns:
        List of 1536 float values representing the embedding vector

    Raises:
        EmbeddingGenerationError: If embedding generation fails after retries

    Example:
        >>> embedding = generate_embedding("Machine learning is a subset of AI")
        >>> len(embedding)
        1536
        >>> isinstance(embedding[0], float)
        True
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding")
        raise EmbeddingGenerationError(
            message="Cannot generate embedding for empty text",
            detail={"text_length": len(text)}
        )

    logger.debug(f"Generating embedding for text ({len(text)} chars)")

    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )

            # Extract embedding vector from response
            embedding = response.data[0].embedding

            logger.debug(
                f"Successfully generated embedding: {len(embedding)} dimensions, "
                f"usage={response.usage.total_tokens} tokens"
            )

            return embedding

        except RateLimitError as e:
            # Rate limit hit - wait and retry
            wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
            logger.warning(
                f"Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Waiting {wait_time}s before retry..."
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached for rate limit")
                raise EmbeddingGenerationError(
                    message="OpenAI rate limit exceeded after retries",
                    detail={
                        "attempt": attempt + 1,
                        "error": str(e)
                    }
                )

        except APITimeoutError as e:
            # Timeout - retry
            wait_time = RETRY_DELAY * (2 ** attempt)
            logger.warning(
                f"API timeout (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Waiting {wait_time}s before retry..."
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached for timeout")
                raise EmbeddingGenerationError(
                    message="OpenAI API timeout after retries",
                    detail={
                        "attempt": attempt + 1,
                        "error": str(e)
                    }
                )

        except APIError as e:
            # General API error - log and raise
            logger.error(f"OpenAI API error: {str(e)}")
            raise EmbeddingGenerationError(
                message=f"OpenAI API error: {str(e)}",
                detail={
                    "error_type": type(e).__name__,
                    "error": str(e)
                }
            )

        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error generating embedding: {str(e)}")
            raise EmbeddingGenerationError(
                message=f"Unexpected error: {str(e)}",
                detail={
                    "error_type": type(e).__name__,
                    "error": str(e)
                }
            )


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in batch.

    More efficient than calling generate_embedding() multiple times.
    OpenAI API supports batching up to 2048 inputs per request.

    Args:
        texts: List of input texts to embed

    Returns:
        List of embedding vectors (one per input text)

    Raises:
        EmbeddingGenerationError: If batch embedding generation fails

    Example:
        >>> texts = [
        ...     "Machine learning is a subset of AI",
        ...     "Neural networks are computational models",
        ...     "Deep learning uses multiple layers"
        ... ]
        >>> embeddings = generate_embeddings_batch(texts)
        >>> len(embeddings)
        3
        >>> len(embeddings[0])
        1536
    """
    if not texts:
        logger.warning("Empty text list provided for batch embedding")
        return []

    # Filter out empty texts
    valid_texts = [text for text in texts if text and text.strip()]

    if not valid_texts:
        logger.warning("All texts are empty after filtering")
        return []

    logger.info(f"Generating embeddings for {len(valid_texts)} texts (batch)")

    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=valid_texts
            )

            # Extract embeddings from response (preserves order)
            embeddings = [item.embedding for item in response.data]

            logger.info(
                f"Successfully generated {len(embeddings)} embeddings, "
                f"total_tokens={response.usage.total_tokens}"
            )

            return embeddings

        except RateLimitError as e:
            # Rate limit hit - wait and retry
            wait_time = RETRY_DELAY * (2 ** attempt)
            logger.warning(
                f"Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Waiting {wait_time}s before retry..."
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached for rate limit")
                raise EmbeddingGenerationError(
                    message="OpenAI rate limit exceeded after retries",
                    detail={
                        "attempt": attempt + 1,
                        "batch_size": len(valid_texts),
                        "error": str(e)
                    }
                )

        except APITimeoutError as e:
            # Timeout - retry
            wait_time = RETRY_DELAY * (2 ** attempt)
            logger.warning(
                f"API timeout (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Waiting {wait_time}s before retry..."
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached for timeout")
                raise EmbeddingGenerationError(
                    message="OpenAI API timeout after retries",
                    detail={
                        "attempt": attempt + 1,
                        "batch_size": len(valid_texts),
                        "error": str(e)
                    }
                )

        except APIError as e:
            # General API error - log and raise
            logger.error(f"OpenAI API error: {str(e)}")
            raise EmbeddingGenerationError(
                message=f"OpenAI API error: {str(e)}",
                detail={
                    "error_type": type(e).__name__,
                    "batch_size": len(valid_texts),
                    "error": str(e)
                }
            )

        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error generating batch embeddings: {str(e)}")
            raise EmbeddingGenerationError(
                message=f"Unexpected error: {str(e)}",
                detail={
                    "error_type": type(e).__name__,
                    "batch_size": len(valid_texts),
                    "error": str(e)
                }
            )
