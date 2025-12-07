"""
Chat handler service.
Orchestrates the complete chat flow: history retrieval, context building, OpenAI call, and response storage.
"""
from typing import Optional, Tuple
from uuid import UUID

from database.repositories import ConversationRepository, MessageRepository, FileRepository
from database.models.message import MessageRole, RetrievalMode
from services.chat_service.context_builder import build_context_with_new_message
from services.chat_service.openai_service import send_chat_completion
from core.utils.logger import setup_logger

logger = setup_logger(__name__)


def handle_chat_request(
    message_text: str,
    conversation_repo: ConversationRepository,
    message_repo: MessageRepository,
    file_repo: FileRepository,
    conversation_id: Optional[UUID] = None,
    file_id: Optional[UUID] = None
) -> Tuple[UUID, str, str, list]:
    """
    Handle a complete chat request flow.

    Orchestrates:
    1. Create or fetch conversation
    2. Fetch conversation history
    3. Build context window (with PDF patching)
    4. Call OpenAI API
    5. Save user message to database (only if OpenAI succeeds)
    6. Save assistant response to database
    7. Return response
    
    Note: Messages are saved AFTER OpenAI call to ensure transactional consistency.
    If OpenAI fails, no orphaned messages are left in the database.

    Args:
        message_text: User's message text
        conversation_repo: ConversationRepository instance
        message_repo: MessageRepository instance
        file_repo: FileRepository instance
        conversation_id: Optional conversation UUID (creates new if None)
        file_id: Optional file UUID to attach to this message

    Returns:
        Tuple of (conversation_id, response_text, retrieval_mode, retrieved_chunks)

    Example:
        >>> conversation_id, response, mode, chunks = handle_chat_request(
        ...     message_text="What is this document about?",
        ...     conversation_repo=conv_repo,
        ...     message_repo=msg_repo,
        ...     file_repo=file_repo,
        ...     conversation_id=None,  # New conversation
        ...     file_id=some_file_uuid
        ... )
    """
    logger.info("Handling chat request")

    # Step 1: Create or fetch conversation
    if conversation_id:
        logger.info(f"Using existing conversation: {conversation_id}")
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            raise ValueError(f"Conversation not found: {conversation_id}")
    else:
        logger.info("Creating new conversation")
        conversation = conversation_repo.create()
        conversation_id = conversation.id
        logger.info(f"Created new conversation: {conversation_id}")

    # Step 2: Fetch conversation history (new message not yet in DB)
    logger.info("Fetching conversation history")
    db_messages = message_repo.get_by_conversation_id(conversation_id)

    # Use all existing messages (new message not yet saved to DB)
    existing_messages = db_messages

    # Step 3: Build context window with PDF patching
    logger.info(f"Building context window from {len(existing_messages)} existing messages + 1 new")
    context_messages = build_context_with_new_message(
        db_messages=existing_messages,
        file_repo=file_repo,
        new_message_text=message_text,
        new_file_id=file_id
    )

    # Step 4: Call OpenAI (before saving to DB)
    logger.info("Calling OpenAI API")
    try:
        assistant_response = send_chat_completion(context_messages)
    except Exception as e:
        logger.error(f"OpenAI API call failed: {str(e)}")
        # Don't save anything if OpenAI fails
        raise

    # Step 5: Save user message to database (only after OpenAI succeeds)
    logger.info("Saving user message to database")
    user_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=message_text,
        file_id=file_id
    )
    logger.debug(f"Saved user message: {user_message.id}")


    # Step 6: Save assistant response to database
    logger.info("Saving assistant response to database")

    # For Milestone 2, we're using inline mode only
    retrieval_mode = RetrievalMode.INLINE
    retrieved_chunks = []  # Empty for inline mode

    assistant_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_response,
        retrieval_mode=retrieval_mode,
        retrieved_chunks=retrieved_chunks
    )
    logger.debug(f"Saved assistant message: {assistant_message.id}")

    # Step 7: Return response
    logger.info("Chat request completed successfully")
    return (
        conversation_id,
        assistant_response,
        retrieval_mode.value,
        retrieved_chunks
    )
