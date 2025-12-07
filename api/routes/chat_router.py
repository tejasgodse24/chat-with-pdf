"""
Chat endpoints.
Handles chat requests and conversation management.
"""
from fastapi import APIRouter, Depends
from uuid import UUID

from api.schemas.request import ChatRequest
from api.schemas.response import (
    ChatResponse,
    RetrievedChunk,
    ConversationListResponse,
    ConversationSummary,
    ConversationDetailResponse,
    MessageResponse
)
from fastapi import Query, HTTPException
from services.chat_service.chat_handler import handle_chat_request
from core.dependencies import get_conversation_repository, get_message_repository, get_file_repository
from database.repositories import ConversationRepository, MessageRepository, FileRepository
from core.utils.logger import setup_logger

logger = setup_logger(__name__)
chat_router = APIRouter(prefix="", tags=["chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
    file_repo: FileRepository = Depends(get_file_repository)
):
    """
    Chat with PDF using inline mode or RAG.

    Handles:
    - Creating new conversations (if conversation_id not provided)
    - Continuing existing conversations
    - Attaching PDF files to messages (if file_id provided)
    - Context window patching with PDFs
    - Multi-turn conversations

    Args:
        request: ChatRequest containing message, conversation_id (optional), file_id (optional)
        conversation_repo: ConversationRepository instance (injected)
        message_repo: MessageRepository instance (injected)
        file_repo: FileRepository instance (injected)

    Returns:
        ChatResponse with conversation_id, response, retrieval_mode, and retrieved_chunks

    Example:
        # First message (new conversation with PDF)
        POST /chat
        {
            "message": "What is this document about?",
            "file_id": "abc-123",
            "conversation_id": null
        }

        # Follow-up message (same conversation)
        POST /chat
        {
            "message": "Tell me about section 2",
            "conversation_id": "conv-456",
            "file_id": null
        }
    """
    logger.info(f"Received chat request: message_length={len(request.message)}")
    logger.debug(f"conversation_id={request.conversation_id}, file_id={request.file_id}")

    # Call chat handler to process request
    conversation_id, response_text, retrieval_mode, retrieved_chunks = handle_chat_request(
        message_text=request.message,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        file_repo=file_repo,
        conversation_id=request.conversation_id,
        file_id=request.file_id
    )

    # Convert retrieved_chunks to response format
    chunk_responses = [
        RetrievedChunk(
            chunk_text=chunk.get("chunk_text", ""),
            similarity_score=chunk.get("similarity_score", 0.0)
        )
        for chunk in retrieved_chunks
    ]

    logger.info(f"Chat request completed: conversation_id={conversation_id}")

    return ChatResponse(
        conversation_id=conversation_id,
        response=response_text,
        retrieval_mode=retrieval_mode,
        retrieved_chunks=chunk_responses
    )


@chat_router.get("/chats", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    message_repo: MessageRepository = Depends(get_message_repository)
):
    """
    List all conversations with pagination.

    Returns conversations ordered by created_at descending (newest first),
    with message count for each conversation.

    Args:
        limit: Maximum number of conversations to return (1-100, default: 20)
        offset: Number of conversations to skip for pagination (default: 0)
        conversation_repo: ConversationRepository instance (injected)
        message_repo: MessageRepository instance (injected)

    Returns:
        ConversationListResponse with paginated conversation list

    Example:
        GET /chats?limit=10&offset=0
    """
    logger.info(f"Fetching conversations list: limit={limit}, offset={offset}")

    # Get total count
    total = conversation_repo.count_all()

    # Get paginated conversations
    conversations = conversation_repo.get_all_paginated(limit=limit, offset=offset)

    # Build conversation summaries with message counts
    conversation_summaries = []
    for conv in conversations:
        message_count = message_repo.count_by_conversation_id(conv.id)
        summary = ConversationSummary(
            conversation_id=conv.id,
            created_at=conv.created_at,
            message_count=message_count
        )
        conversation_summaries.append(summary)

    logger.info(f"Successfully fetched {len(conversation_summaries)} conversations (total: {total})")

    return ConversationListResponse(
        chats=conversation_summaries,
        total=total,
        limit=limit,
        offset=offset
    )


@chat_router.get("/chats/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    message_repo: MessageRepository = Depends(get_message_repository)
):
    """
    Get specific conversation with all messages.

    Returns full conversation history including all messages with their metadata.

    Args:
        conversation_id: UUID of the conversation to retrieve
        conversation_repo: ConversationRepository instance (injected)
        message_repo: MessageRepository instance (injected)

    Returns:
        ConversationDetailResponse with conversation details and all messages

    Raises:
        HTTPException 404: If conversation doesn't exist

    Example:
        GET /chats/550e8400-e29b-41d4-a716-446655440000
    """
    logger.info(f"Fetching conversation detail: {conversation_id}")

    # Get conversation
    conversation = conversation_repo.get_by_id(conversation_id)
    if not conversation:
        logger.warning(f"Conversation not found: {conversation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}"
        )

    # Get all messages for this conversation
    db_messages = message_repo.get_by_conversation_id(conversation_id)

    # Convert messages to response format
    message_responses = []
    for msg in db_messages:
        # Convert retrieved_chunks if present
        chunks = None
        if msg.retrieved_chunks:
            chunks = [
                RetrievedChunk(
                    chunk_text=chunk.get("chunk_text", ""),
                    similarity_score=chunk.get("similarity_score", 0.0)
                )
                for chunk in msg.retrieved_chunks
            ]

        msg_response = MessageResponse(
            role=msg.role.value,
            content=msg.content,
            file_id=msg.file_id,
            retrieval_mode=msg.retrieval_mode.value if msg.retrieval_mode else None,
            retrieved_chunks=chunks,
            created_at=msg.created_at
        )
        message_responses.append(msg_response)

    logger.info(f"Successfully fetched conversation with {len(message_responses)} messages")

    return ConversationDetailResponse(
        conversation_id=conversation.id,
        created_at=conversation.created_at,
        messages=message_responses
    )
