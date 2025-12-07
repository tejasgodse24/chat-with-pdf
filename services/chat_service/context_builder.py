"""
Context window builder for chat completions.
Builds OpenAI-compatible message history from database messages with PDF patching.
Implements OpenAI file size constraints and message limits.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
import json
from database.models.message import Message, MessageRole, RetrievalMode
from database.models.file import IngestionStatus
from database.repositories import FileRepository
from services.file_service.s3_service import download_pdf_from_s3
from core.utils.helpers import encode_pdf_to_base64
from services.chat_service.message_builder import build_user_message, build_assistant_message
from core.utils.logger import setup_logger

logger = setup_logger(__name__)

# OpenAI constraints
MAX_MESSAGES = 20  # Keep last 20 messages
MAX_TOTAL_FILE_SIZE_MB = 50  # Total file size limit
MAX_SINGLE_FILE_SIZE_MB = 50  # Per-file size limit


def categorize_files_by_ingestion_status(
    db_messages: List[Message],
    file_repo: FileRepository,
    new_file_id: Optional[UUID] = None
) -> tuple[List[UUID], List[UUID]]:
    """
    Categorize files into inline vs RAG based on ingestion_status.

    Collects all unique file_ids from conversation messages and categorizes them:
    - ingestion_status = "uploaded" → inline_files (use base64 PDF)
    - ingestion_status = "completed" → rag_files (use vector search)
    - ingestion_status = "failed" → skip (don't include)

    This enables dynamic mode switching:
    - Inline mode: Files still processing, send as base64 to LLM
    - RAG mode: Files fully ingested, use semantic search with tool calling

    Uses eagerly loaded file relationships from messages to avoid N+1 queries.
    Only fetches new_file separately if provided.

    Args:
        db_messages: List of Message ORM objects with eagerly loaded file relationships
        file_repo: FileRepository instance (only used for new_file_id)
        new_file_id: Optional file_id from new message (not yet in db_messages)

    Returns:
        Tuple of (inline_file_ids, rag_file_ids)
        - inline_file_ids: List of UUIDs with status "uploaded"
        - rag_file_ids: List of UUIDs with status "completed"

    Example:
        >>> inline_ids, rag_ids = categorize_files_by_ingestion_status(
        ...     db_messages=existing_messages,
        ...     file_repo=file_repo,
        ...     new_file_id=new_file_uuid
        ... )
        >>> # Use inline_ids for base64 patching
        >>> # Use rag_ids for vector search filtering
    """
    logger.info(
        f"Categorizing files from {len(db_messages)} messages "
        f"(new_file_id={'present' if new_file_id else 'none'})"
    )

    # Track seen files to avoid duplicates
    seen_files = {}
    inline_file_ids = []
    rag_file_ids = []
    failed_count = 0
    not_found_count = 0

    # Process files from existing messages (use eagerly loaded relationships)
    for msg in db_messages:
        if msg.file_id and msg.file_id not in seen_files:
            # Use eagerly loaded file relationship (avoids N+1 query)
            db_file = msg.file
            
            if not db_file:
                logger.warning(f"File not found in relationship: {msg.file_id}")
                not_found_count += 1
                seen_files[msg.file_id] = None
                continue

            # Mark as seen
            seen_files[msg.file_id] = db_file

            # Categorize based on ingestion_status
            if db_file.ingestion_status == IngestionStatus.UPLOADED:
                inline_file_ids.append(msg.file_id)
                logger.debug(
                    f"File {msg.file_id} → inline mode (status: uploaded)"
                )
            elif db_file.ingestion_status == IngestionStatus.COMPLETED:
                rag_file_ids.append(msg.file_id)
                logger.debug(
                    f"File {msg.file_id} → RAG mode (status: completed)"
                )
            elif db_file.ingestion_status == IngestionStatus.FAILED:
                failed_count += 1
                logger.warning(
                    f"File {msg.file_id} skipped (status: failed, "
                    f"error: {db_file.error_message or 'unknown'})"
                )
            else:
                logger.warning(
                    f"File {msg.file_id} has unknown status: {db_file.ingestion_status}"
                )

    # Handle new_file_id separately (not in db_messages yet)
    if new_file_id and new_file_id not in seen_files:
        # Fetch new file from database (single query)
        db_file = file_repo.get_by_id(new_file_id)
        
        if not db_file:
            logger.warning(f"New file not found in database: {new_file_id}")
            not_found_count += 1
        else:
            # Categorize new file
            if db_file.ingestion_status == IngestionStatus.UPLOADED:
                inline_file_ids.append(new_file_id)
                logger.debug(
                    f"New file {new_file_id} → inline mode (status: uploaded)"
                )
            elif db_file.ingestion_status == IngestionStatus.COMPLETED:
                rag_file_ids.append(new_file_id)
                logger.debug(
                    f"New file {new_file_id} → RAG mode (status: completed)"
                )
            elif db_file.ingestion_status == IngestionStatus.FAILED:
                failed_count += 1
                logger.warning(
                    f"New file {new_file_id} skipped (status: failed, "
                    f"error: {db_file.error_message or 'unknown'})"
                )
            else:
                logger.warning(
                    f"New file {new_file_id} has unknown status: {db_file.ingestion_status}"
                )

    # Log summary
    logger.info(
        f"File categorization complete: "
        f"{len(inline_file_ids)} inline, "
        f"{len(rag_file_ids)} RAG, "
        f"{failed_count} failed, "
        f"{not_found_count} not found"
    )

    return inline_file_ids, rag_file_ids


def collect_all_files_from_conversation(
    all_messages: List[Message],
    file_repo: FileRepository,
    inline_file_ids: Optional[List[UUID]] = None
) -> List[Dict[str, Any]]:
    """
    Collect ONLY inline files from conversation (skip RAG files).

    Downloads and processes only files in inline_file_ids list.
    Files with status "completed" (RAG mode) should NOT be downloaded.

    This implements Milestone 4 requirement:
    - If ingestion_status = "uploaded": Download and convert to base64 (inline mode)
    - If ingestion_status = "completed": DO NOT download (use vector search instead)

    Args:
        all_messages: ALL messages in conversation (not just recent)
        file_repo: FileRepository instance
        inline_file_ids: List of file UUIDs to download (files with status "uploaded").
                        If None, downloads ALL files (backward compatible).
                        If empty list, downloads NO files (RAG-only mode).

    Returns:
        List of file dictionaries with metadata:
        [
            {
                'file_id': UUID,
                'filename': str,
                'size_bytes': int,
                'base64': str,
                'first_mentioned_at': datetime
            }
        ]
    """
    logger.info(
        f"Collecting files from {len(all_messages)} total messages "
        f"(inline_filter={'all' if inline_file_ids is None else len(inline_file_ids)} files)"
    )

    # Convert to set for O(1) lookup
    inline_ids_set = set(inline_file_ids) if inline_file_ids else set()
    seen_files = {}

    for msg in all_messages:
        logger.info(str(msg))
        # if msg.file_id and msg.file_id not in seen_files:
        #     # CRITICAL: Skip if not in inline_file_ids (i.e., RAG mode files)
        #     if inline_ids_set is not None and msg.file_id not in inline_ids_set:
        #         logger.debug(
        #             f"Skipping file {msg.file_id} (RAG mode - will use vector search)"
        #         )
        #         continue
        if msg.file_id in inline_ids_set:
            try:
                # Use eagerly loaded file relationship (from DB messages)
                db_file = msg.file
                if not db_file:
                    logger.warning(f"File not found in DB: {msg.file_id}")
                    continue

                # Download PDF from S3 (only for inline files)
                pdf_bytes = download_pdf_from_s3(db_file.s3_key)
                size_mb = len(pdf_bytes) / (1024 * 1024)

                # Check per-file size limit
                if size_mb > MAX_SINGLE_FILE_SIZE_MB:
                    logger.warning(
                        f"File {msg.file_id} ({size_mb:.2f} MB) exceeds "
                        f"{MAX_SINGLE_FILE_SIZE_MB} MB limit. Skipping."
                    )
                    continue

                # Store file data
                seen_files[msg.file_id] = {
                    'file_id': msg.file_id,
                    'filename': db_file.s3_key.split('/')[-1],
                    'size_bytes': len(pdf_bytes),
                    'base64': encode_pdf_to_base64(pdf_bytes),
                    'first_mentioned_at': msg.created_at
                }

                logger.debug(
                    f"Collected inline file: {db_file.s3_key} ({size_mb:.2f} MB)"
                )

            except Exception as e:
                logger.error(f"Error processing file {msg.file_id}: {str(e)}")
                continue

    logger.info(
        f"Collected {len(seen_files)} inline files from conversation "
        f"(skipped {len([m for m in all_messages if m.file_id]) - len(seen_files)} RAG files)"
    )
    return list(seen_files.values())


def select_files_within_limit(
    files: List[Dict[str, Any]],
    max_size_mb: float = MAX_TOTAL_FILE_SIZE_MB
) -> List[Dict[str, Any]]:
    """
    Select files that fit within total size limit, prioritizing newest.

    Args:
        files: List of file dictionaries from collect_all_files_from_conversation
        max_size_mb: Maximum total size in MB (default: 50 MB)

    Returns:
        List of selected files (newest first, within size limit)
    """
    if not files:
        return []

    # Sort by first mentioned (newest first)
    sorted_files = sorted(
        files,
        key=lambda f: f['first_mentioned_at'],
        reverse=True
    )

    selected = []
    total_bytes = 0
    max_bytes = max_size_mb * 1024 * 1024

    for file in sorted_files:
        if total_bytes + file['size_bytes'] <= max_bytes:
            selected.append(file)
            total_bytes += file['size_bytes']
            logger.debug(f"Selected file: {file['filename']} ({file['size_bytes'] / (1024*1024):.2f} MB)")
        else:
            logger.info(
                f"Skipping file {file['filename']} "
                f"({file['size_bytes'] / (1024*1024):.2f} MB) - would exceed {max_size_mb} MB limit"
            )

    total_mb = total_bytes / (1024 * 1024)
    logger.info(f"Selected {len(selected)} files totaling {total_mb:.2f} MB")

    return selected


def get_recent_messages(
    all_messages: List[Message],
    max_messages: int = MAX_MESSAGES
) -> List[Message]:
    """
    Get last N messages from conversation.

    Args:
        all_messages: All messages in conversation
        max_messages: Maximum messages to include (default: 20)

    Returns:
        Last N messages (chronologically ordered)
    """
    if len(all_messages) <= max_messages:
        return all_messages

    recent = all_messages[-max_messages:]
    logger.info(
        f"Limiting conversation from {len(all_messages)} to {max_messages} messages "
        f"(dropped {len(all_messages) - max_messages} oldest messages)"
    )

    return recent


def build_context_window(
    db_messages: List[Message],
    file_repo: FileRepository,
    inline_file_ids: Optional[List[UUID]] = None
) -> tuple[List[Dict[str, Any]], set]:
    """
    Build context window with OpenAI file size constraints and message limits.

    Supports hybrid mode: Only processes files in inline_file_ids list.
    Files with status "completed" (RAG mode) should NOT be in inline_file_ids.

    Strategy:
    1. Collect files from conversation (filtered by inline_file_ids if provided)
    2. Select files that fit within 50 MB (newest first)
    3. Keep only last 20 messages
    4. Group all selected files at start of conversation
    5. Build remaining messages as text only

    Args:
        db_messages: List of ALL Message ORM objects (ordered chronologically)
        file_repo: FileRepository instance
        inline_file_ids: Optional list of file UUIDs to include as base64.
                        If None, includes ALL files (backward compatible).
                        If empty list, includes NO files (RAG-only mode).

    Returns:
        Tuple of (formatted_messages, included_file_ids)

    Example:
        >>> # Hybrid mode: Only inline files
        >>> inline_ids = [uuid1, uuid2]  # Files with status "uploaded"
        >>> context, file_ids = build_context_window(
        ...     all_messages, file_repo, inline_file_ids=inline_ids
        ... )
        >>> response = send_chat_completion(context)
    """
    logger.info(
        f"Building context window from {len(db_messages)} total messages "
        f"(inline_file_ids={'all' if inline_file_ids is None else len(inline_file_ids)})"
    )

    if not db_messages:
        return [], set()

    # Step 1: Collect ONLY inline files (filtering happens inside collect function)
    # RAG files are NOT downloaded - they'll be retrieved via vector search
    all_files = collect_all_files_from_conversation(
        db_messages,
        file_repo,
        inline_file_ids=inline_file_ids  # Pass filter directly
    )

    # Step 2: Select files within 50 MB limit (newest first)
    selected_files = select_files_within_limit(all_files)

    # Step 3: Keep only last 20 messages
    recent_messages = get_recent_messages(db_messages)

    # Step 4: Build context with files grouped at start
    formatted_messages = []
    included_file_ids = {f['file_id'] for f in selected_files}

    for idx, msg in enumerate(recent_messages):
        if idx == 0 and msg.role == MessageRole.USER:
            # First user message: Include ALL selected files
            content_parts = []

            # Add all files first
            for file in selected_files:
                content_parts.append({
                    "type": "input_file",
                    "filename": file['filename'],
                    "file_data": f"data:application/pdf;base64,{file['base64']}"
                })

            # Then add the message text
            content_parts.append({
                "type": "input_text",
                "text": msg.content
            })

            formatted_messages.append({
                "role": "user",
                "content": content_parts
            })

            logger.debug(f"Added {len(selected_files)} files to first message")

        elif msg.role == MessageRole.USER:
            # User messages: Check if this message has a file_id
            # Even if file is in RAG mode (not downloaded), we should indicate it
            if msg.file_id and msg.file_id not in included_file_ids:
                # File was attached but not included as base64 (RAG mode)
                # Add a note to help LLM understand file context
                file_info = ""
                if msg.file:
                    filename = msg.file.s3_key.split('/')[-1]
                    file_info = f" [Referring to file: {filename}]"

                formatted_messages.append({
                    "role": "user",
                    "content": f"{msg.content}{file_info}"
                })
            else:
                # Just text (no file attached to this message)
                formatted_messages.append({
                    "role": "user",
                    "content": msg.content
                })

        elif msg.role == MessageRole.ASSISTANT:
            # ALWAYS add assistant message FIRST
            formatted_messages.append({
                "role": "assistant",
                "content": msg.content
            })
            
            # If RAG mode, add chunks AFTER the assistant message
            if msg.retrieval_mode == RetrievalMode.RAG and msg.retrieved_chunks:
                # Format all chunks into a single system message
                chunks_text_parts = ["Context used for this response:\n"]
                
                for idx, chunk in enumerate(msg.retrieved_chunks, 1):
                    chunk_text = chunk.get("chunk_text", "")
                    score = chunk.get("similarity_score", 0.0)
                    
                    if chunk_text:
                        chunks_text_parts.append(
                            f"\n[Chunk {idx}] (relevance: {score:.1%})\n{chunk_text}"
                        )
                
                # Combine all chunks into single content
                chunks_content = "\n".join(chunks_text_parts)
                
                # Add as ONE system message
                formatted_messages.append({
                    "role": "system",
                    "content": chunks_content
                })

        else:
            logger.warning(f"Unknown message role: {msg.role}. Skipping message.")

    # Log summary
    total_file_size_mb = sum(f['size_bytes'] for f in selected_files) / (1024 * 1024)
    logger.info(
        f"Built context: {len(formatted_messages)} messages, "
        f"{len(selected_files)} files ({total_file_size_mb:.2f} MB total)"
    )

    return formatted_messages, included_file_ids


def build_context_with_new_message(
    db_messages: List[Message],
    file_repo: FileRepository,
    new_message_text: str,
    new_file_id: Optional[UUID] = None
) -> List[Dict[str, Any]]:
    """
    Build context window including a new user message.

    This is a simplified wrapper that creates a temporary message object
    and calls build_context_window with all messages.

    NOTE: With the new file grouping strategy, all files (including from
    the new message) will be grouped at the start of the conversation.

    Args:
        db_messages: List of existing Message ORM objects from database
        file_repo: FileRepository instance for fetching file metadata
        new_message_text: Text content of the new user message
        new_file_id: Optional file UUID to attach to new message

    Returns:
        List of formatted messages including the new message

    Example:
        >>> # Build context with existing messages + new message
        >>> context = build_context_with_new_message(
        ...     db_messages=existing_messages,
        ...     file_repo=file_repo,
        ...     new_message_text="What about section 2?",
        ...     new_file_id=None  # No new file
        ... )
        >>> response = send_chat_completion(context)
    """
    logger.info(f"Building context with {len(db_messages)} existing messages + 1 new message")

    # Create a temporary message object for the new message
    from datetime import datetime, timezone
    from uuid import uuid4

    temp_new_message = Message(
        id=uuid4(),
        conversation_id=db_messages[0].conversation_id if db_messages else uuid4(),
        role=MessageRole.USER,
        content=new_message_text,
        file_id=new_file_id,
        created_at=datetime.now(timezone.utc)
    )

    # If new message has a file, load the file relationship manually
    # (since temp message is not from DB, relationship isn't loaded)
    if new_file_id:
        temp_new_message.file = file_repo.get_by_id(new_file_id)

    # Combine all messages
    all_messages = list(db_messages) + [temp_new_message]

    # Build context with ALL messages (will apply constraints automatically)
    formatted_messages, _ = build_context_window(all_messages, file_repo)

    logger.info(f"Final context has {len(formatted_messages)} messages")
    return formatted_messages


def build_context_with_retrieved_chunks(
    original_messages: List[Dict[str, Any]],
    retrieved_chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Append retrieved chunks to context as a system message for RAG mode.

    Takes the original conversation context and adds retrieved chunks
    from vector search as a system message at the end. This provides
    the LLM with relevant document context to answer the user's question.

    Args:
        original_messages: List of formatted messages from build_context_window
        retrieved_chunks: List of chunk dictionaries from query_vectors:
                         [
                             {
                                 "id": "chunk-uuid",
                                 "score": 0.92,
                                 "metadata": {
                                     "file_id": "file-uuid",
                                     "chunk_id": "chunk-uuid",
                                     "chunk_text": "..."
                                 }
                             },
                             ...
                         ]

    Returns:
        List of messages with chunks appended as system message

    Example:
        >>> # After tool call, retrieve chunks
        >>> results = query_vectors(query_vector, top_k=5, file_ids=rag_file_ids)
        >>> 
        >>> # Add chunks to context
        >>> context_with_chunks = build_context_with_retrieved_chunks(
        ...     original_messages=context_messages,
        ...     retrieved_chunks=results
        ... )
        >>> 
        >>> # Call LLM again with chunks
        >>> final_response = send_chat_completion(context_with_chunks)
    """
    logger.info(
        f"Building context with {len(retrieved_chunks)} retrieved chunks "
        f"(original messages: {len(original_messages)})"
    )

    if not retrieved_chunks:
        logger.warning("No chunks retrieved, returning original context")
        return original_messages

    # Format chunks into readable text
    chunks_text_parts = []
    chunks_text_parts.append("Retrieved relevant information from documents:\n")

    for idx, chunk in enumerate(retrieved_chunks, 1):
        # Extract chunk text from metadata
        chunk_text = chunk.get("metadata", {}).get("chunk_text", "")
        similarity_score = chunk.get("score", 0.0)

        if chunk_text:
            # Format: [Chunk N] (relevance: XX%) text...
            chunks_text_parts.append(
                f"\n[Chunk {idx}] (relevance: {similarity_score:.1%})\n{chunk_text}"
            )
            logger.debug(
                f"Chunk {idx}: {len(chunk_text)} chars, score={similarity_score:.3f}"
            )
        else:
            logger.warning(f"Chunk {idx} has no text, skipping")

    # Combine all chunks into single text
    chunks_content = "\n".join(chunks_text_parts)

    # Create system message with chunks
    system_message = {
        "role": "system",
        "content": chunks_content
    }

    # Append to original messages
    messages_with_chunks = original_messages + [system_message]

    logger.info(
        f"Added {len(retrieved_chunks)} chunks as system message "
        f"({len(chunks_content)} characters total)"
    )

    return messages_with_chunks
