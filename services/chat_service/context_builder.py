"""
Context window builder for chat completions.
Builds OpenAI-compatible message history from database messages with PDF patching.
Implements OpenAI file size constraints and message limits.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID

from database.models.message import Message, MessageRole
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


def collect_all_files_from_conversation(
    all_messages: List[Message],
    file_repo: FileRepository
) -> List[Dict[str, Any]]:
    """
    Collect all unique files from entire conversation with metadata.

    Downloads and processes all files mentioned in the conversation,
    checking per-file size limits.

    Args:
        all_messages: ALL messages in conversation (not just recent)
        file_repo: FileRepository instance

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
    logger.info(f"Collecting files from {len(all_messages)} total messages")

    seen_files = {}

    for msg in all_messages:
        if msg.file_id and msg.file_id not in seen_files:
            try:
                # Use eagerly loaded file relationship (from DB messages)
                db_file = msg.file
                if not db_file:
                    logger.warning(f"File not found in DB: {msg.file_id}")
                    continue

                # Download PDF from S3
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

                logger.debug(f"Collected file: {db_file.s3_key} ({size_mb:.2f} MB)")

            except Exception as e:
                logger.error(f"Error processing file {msg.file_id}: {str(e)}")
                continue

    logger.info(f"Collected {len(seen_files)} unique files from conversation")
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
    file_repo: FileRepository
) -> tuple[List[Dict[str, Any]], set]:
    """
    Build context window with OpenAI file size constraints and message limits.

    Strategy:
    1. Collect ALL unique files from entire conversation
    2. Select files that fit within 50 MB (newest first)
    3. Keep only last 20 messages
    4. Group all selected files at start of conversation
    5. Build remaining messages as text only

    Args:
        db_messages: List of ALL Message ORM objects (ordered chronologically)
        file_repo: FileRepository instance

    Returns:
        Tuple of (formatted_messages, included_file_ids)

    Example:
        >>> all_messages = message_repo.get_by_conversation_id(conversation_id)
        >>> context, file_ids = build_context_window(all_messages, file_repo)
        >>> response = send_chat_completion(context)
    """
    logger.info(f"Building context window from {len(db_messages)} total messages")

    if not db_messages:
        return [], set()

    # Step 1: Collect ALL files from entire conversation
    all_files = collect_all_files_from_conversation(db_messages, file_repo)

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
            # Other user messages: Just text
            formatted_messages.append({
                "role": "user",
                "content": msg.content
            })

        elif msg.role == MessageRole.ASSISTANT:
            # Assistant messages: Just text
            formatted_messages.append({
                "role": "assistant",
                "content": msg.content
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
