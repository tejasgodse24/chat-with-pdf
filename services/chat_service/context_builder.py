"""
Context window builder for chat completions.
Builds OpenAI-compatible message history from database messages with PDF patching.
"""
from typing import List, Dict, Any
from uuid import UUID

from database.models.message import Message, MessageRole
from database.repositories import FileRepository
from services.file_service.s3_service import download_pdf_from_s3
from core.utils.helpers import encode_pdf_to_base64
from services.chat_service.message_builder import build_user_message, build_assistant_message
from core.utils.logger import setup_logger

logger = setup_logger(__name__)


def build_context_window(
    db_messages: List[Message],
    file_repo: FileRepository
) -> List[Dict[str, Any]]:
    """
    Build context window from database messages with PDF patching.

    Iterates through conversation history and patches PDFs where needed.
    Downloads PDFs from S3 and converts to base64 for messages that have file attachments.

    Args:
        db_messages: List of Message ORM objects from database (ordered chronologically)
        file_repo: FileRepository instance for fetching file metadata

    Returns:
        List of formatted messages ready for OpenAI Chat Completions API

    Example:
        >>> messages = message_repo.get_by_conversation_id(conversation_id)
        >>> context = build_context_window(messages, file_repo)
        >>> response = send_chat_completion(context)
    """
    logger.info(f"Building context window from {len(db_messages)} messages")

    formatted_messages = []
    included_file_ids = set()

    for msg in db_messages:
        if msg.role == MessageRole.USER:
            # User message - may have PDF attachment
            if msg.file_id and not msg.file_id in included_file_ids:    #dont include files again and again
                # Message has file - download and patch PDF
                logger.debug(f"Processing user message with file_id: {msg.file_id}")

                try:
                    # Get file metadata from database
                    db_file = file_repo.get_by_id(msg.file_id)
                    if not db_file:
                        logger.warning(f"File not found: {msg.file_id}. Skipping PDF attachment.")
                        # Build message without PDF
                        formatted_msg = build_user_message(text=msg.content)
                    else:
                        # Download PDF from S3
                        pdf_bytes = download_pdf_from_s3(db_file.s3_key)

                        # Encode to base64
                        pdf_base64 = encode_pdf_to_base64(pdf_bytes)

                        # Build message with PDF
                        filename = db_file.s3_key.split('/')[-1]  # Extract filename from s3_key
                        formatted_msg = build_user_message(
                            text=msg.content,
                            pdf_base64=pdf_base64,
                            filename=filename
                        )

                        included_file_ids.add(msg.file_id)

                        logger.debug(f"Successfully attached PDF to message: {filename}")

                except Exception as e:
                    logger.error(f"Error processing PDF for message {msg.id}: {str(e)}")
                    # Fallback: build message without PDF
                    formatted_msg = build_user_message(text=msg.content)

            else:
                # User message without file - simple text
                logger.debug("Processing user message without file")
                formatted_msg = build_user_message(text=msg.content)

            formatted_messages.append(formatted_msg)

        elif msg.role == MessageRole.ASSISTANT:
            # Assistant message - always plain text
            logger.debug("Processing assistant message")
            formatted_msg = build_assistant_message(text=msg.content)
            formatted_messages.append(formatted_msg)

        else:
            logger.warning(f"Unknown message role: {msg.role}. Skipping message.")

    logger.info(f"Built context window with {len(formatted_messages)} formatted messages")
    return formatted_messages, included_file_ids


def build_context_with_new_message(
    db_messages: List[Message],
    file_repo: FileRepository,
    new_message_text: str,
    new_file_id: UUID = None
) -> List[Dict[str, Any]]:
    """
    Build context window including a new user message.

    Convenience function that builds context from existing messages
    and appends a new user message (with optional file).

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

    # Build context from existing messages
    formatted_messages, included_file_ids = build_context_window(db_messages, file_repo)

    # Add new user message
    if new_file_id and not new_file_id in included_file_ids:
        logger.debug(f"Adding new user message with file_id: {new_file_id}")
        try:
            # Get file and build message with PDF
            db_file = file_repo.get_by_id(new_file_id)
            if db_file:
                pdf_bytes = download_pdf_from_s3(db_file.s3_key)
                pdf_base64 = encode_pdf_to_base64(pdf_bytes)
                filename = db_file.s3_key.split('/')[-1]

                new_msg = build_user_message(
                    text=new_message_text,
                    pdf_base64=pdf_base64,
                    filename=filename
                )
            else:
                logger.warning(f"File not found: {new_file_id}. Adding message without PDF.")
                new_msg = build_user_message(text=new_message_text)

        except Exception as e:
            logger.error(f"Error processing new message PDF: {str(e)}")
            new_msg = build_user_message(text=new_message_text)
    else:
        logger.debug("Adding new user message without file")
        new_msg = build_user_message(text=new_message_text)

    formatted_messages.append(new_msg)

    logger.info(f"Final context has {len(formatted_messages)} messages")
    return formatted_messages
