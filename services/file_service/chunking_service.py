"""
Text chunking service for RAG pipeline.
Implements fixed-size chunking with overlap using tiktoken for accurate token counting.
"""
import re
from typing import List, Dict, Any
from core.utils.logger import setup_logger

try:
    import tiktoken
except ImportError:
    raise ImportError(
        "tiktoken is required for chunking. Install with: pip install tiktoken"
    )

logger = setup_logger(__name__)

# Chunking parameters (as discussed)
DEFAULT_CHUNK_SIZE = 512  # tokens
DEFAULT_OVERLAP = 100  # tokens (20% of chunk_size)
ENCODING_MODEL = "text-embedding-3-small"  # Match the embedding model


def clean_text(text: str) -> str:
    """
    Clean extracted PDF text for better chunking.

    Handles common PDF extraction issues:
    - Excessive whitespace
    - Hyphenation across lines
    - Multiple consecutive line breaks

    Args:
        text: Raw text extracted from PDF

    Returns:
        Cleaned text ready for chunking

    Example:
        >>> raw = "Machine  learning\\n\\nis\\n\\n\\na subset of AI"
        >>> clean_text(raw)
        "Machine learning is a subset of AI"
    """
    # Remove excessive whitespace (multiple spaces/tabs)
    text = re.sub(r'[ \t]+', ' ', text)

    # Fix hyphenation across lines (e.g., "compu-\ntational" → "computational")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Normalize line breaks (replace multiple newlines with double newline)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Chunk text into fixed-size chunks with overlap using tiktoken.

    Strategy:
    - Fixed-size chunks of 512 tokens (default)
    - 20% overlap between consecutive chunks (100 tokens default)
    - Uses tiktoken for accurate OpenAI token counting

    Args:
        text: Input text to chunk
        chunk_size: Size of each chunk in tokens (default: 512)
        overlap: Overlap between chunks in tokens (default: 100)

    Returns:
        List of chunk dictionaries with metadata:
        [
            {
                "chunk_index": 0,
                "chunk_text": "...",
                "chunk_tokens": 512,
                "start_char": 0,
                "end_char": 2048
            },
            ...
        ]

    Example:
        >>> text = "Machine learning is a subset of AI. " * 100
        >>> chunks = chunk_text(text, chunk_size=512, overlap=100)
        >>> len(chunks)  # Number of chunks created
        3
        >>> chunks[0]["chunk_tokens"]
        512
    """
    logger.info(
        f"Starting chunking: text_length={len(text)}, "
        f"chunk_size={chunk_size}, overlap={overlap}"
    )

    # Handle empty or very short text
    if not text or not text.strip():
        logger.warning("Empty text provided for chunking")
        return []

    # Get tokenizer for the embedding model
    try:
        encoder = tiktoken.encoding_for_model(ENCODING_MODEL)
    except KeyError:
        # Fallback to cl100k_base if model not found
        logger.warning(f"Model {ENCODING_MODEL} not found, using cl100k_base encoding")
        encoder = tiktoken.get_encoding("cl100k_base")

    # Encode full text to tokens
    tokens = encoder.encode(text)
    total_tokens = len(tokens)

    logger.info(f"Text encoded to {total_tokens} tokens")

    # Handle text shorter than chunk_size
    if total_tokens <= chunk_size:
        logger.info("Text fits in single chunk")
        return [{
            "chunk_index": 0,
            "chunk_text": text,
            "chunk_tokens": total_tokens,
            "start_char": 0,
            "end_char": len(text)
        }]

    # Calculate step size (chunk_size - overlap)
    step = chunk_size - overlap

    if step <= 0:
        logger.error(f"Invalid chunking params: overlap ({overlap}) >= chunk_size ({chunk_size})")
        raise ValueError(
            f"Overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    # Create chunks
    chunks = []
    chunk_index = 0

    for i in range(0, total_tokens, step):
        # Get token slice for this chunk
        chunk_tokens = tokens[i:i + chunk_size]

        # Decode tokens back to text
        chunk_text = encoder.decode(chunk_tokens)

        # Calculate character positions (approximate)
        # Note: Token boundaries don't always align with character boundaries
        start_char = len(encoder.decode(tokens[:i])) if i > 0 else 0
        end_char = start_char + len(chunk_text)

        # Create chunk metadata
        chunk = {
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_tokens": len(chunk_tokens),
            "start_char": start_char,
            "end_char": end_char
        }

        chunks.append(chunk)
        chunk_index += 1

        logger.debug(
            f"Created chunk {chunk_index}: tokens={len(chunk_tokens)}, "
            f"chars={len(chunk_text)}"
        )

        # Stop if we've covered all tokens
        if i + chunk_size >= total_tokens:
            break

    logger.info(
        f"Chunking complete: created {len(chunks)} chunks, "
        f"avg_tokens={total_tokens/len(chunks):.1f}"
    )

    return chunks


def chunk_pdf_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    clean: bool = True
) -> List[Dict[str, Any]]:
    """
    Clean and chunk PDF text in one operation.

    Convenience function that combines text cleaning and chunking.
    Recommended for PDF text that needs preprocessing.

    Args:
        text: Raw PDF text
        chunk_size: Size of each chunk in tokens (default: 512)
        overlap: Overlap between chunks in tokens (default: 100)
        clean: Whether to clean text before chunking (default: True)

    Returns:
        List of chunk dictionaries with metadata

    Example:
        >>> raw_pdf_text = extract_text_from_pdf(pdf_bytes)
        >>> chunks = chunk_pdf_text(raw_pdf_text)
        >>> for chunk in chunks:
        ...     print(f"Chunk {chunk['chunk_index']}: {chunk['chunk_tokens']} tokens")
    """
    logger.info("Chunking PDF text")

    # Clean text if requested
    if clean:
        logger.debug("Cleaning PDF text before chunking")
        text = clean_text(text)

    # Chunk the text
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    return chunks
