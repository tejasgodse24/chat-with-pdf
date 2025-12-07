"""
Chat handler service.
Orchestrates the complete chat flow: history retrieval, context building, OpenAI call, and response storage.
"""
from typing import Optional, Tuple, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from database.repositories import ConversationRepository, MessageRepository, FileRepository
from database.models.message import Message, MessageRole, RetrievalMode
from services.chat_service.context_builder import (
    categorize_files_by_ingestion_status,
    build_context_window,
    build_context_with_retrieved_chunks
)
from services.chat_service.openai_service import (
    send_chat_completion,
    send_chat_completion_with_tools,
    SEMANTIC_SEARCH_TOOL
)
from services.vector_service.embeddings_service import generate_embedding
from services.vector_service.upstash_service import query_vectors
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

    # Step 2: Fetch conversation history with files eagerly loaded (avoids N+1 queries)
    logger.info("Fetching conversation history with files")
    db_messages = message_repo.get_by_conversation_id_with_files(conversation_id)

    # Create temporary message for new user input
    temp_new_message = Message(
        id=uuid4(),
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=message_text,
        file_id=file_id,
        created_at=datetime.now(timezone.utc)
    )
    
    # Load file relationship for new message if needed
    if file_id:
        temp_new_message.file = file_repo.get_by_id(file_id)
    
    # Combine all messages
    all_messages = list(db_messages) + [temp_new_message]

    # Step 3: Categorize files by ingestion status (Milestone 4)
    logger.info("Categorizing files by ingestion status")
    inline_file_ids, rag_file_ids = categorize_files_by_ingestion_status(
        db_messages=db_messages,
        file_repo=file_repo,
        new_file_id=file_id
    )
    
    logger.info(
        f"File categorization: {len(inline_file_ids)} inline, {len(rag_file_ids)} RAG"
    )

    # Step 4: Build context window with only inline files (hybrid mode)
    logger.info(f"Building context from {len(db_messages)} messages + 1 new")
    
    
    
    # Build context with only inline files
    context_messages, _ = build_context_window(
        db_messages=all_messages,
        file_repo=file_repo,
        inline_file_ids=inline_file_ids  # Only inline files as base64
    )
    
    # Step 4.5: Add historical RAG chunks to context (Case 1)
    # For messages that used RAG mode, append their retrieved chunks
    # context_messages = _append_historical_rag_chunks(context_messages, db_messages)

    # Step 5: Decide between inline and RAG mode
    # Use tool calling if ANY RAG files exist (new OR historical)
    assistant_response = None
    retrieval_mode = RetrievalMode.INLINE
    retrieved_chunks = []
    
    if len(rag_file_ids) > 0:
        # RAG mode: Conversation has completed files - use tool calling
        logger.info(f"RAG mode available: {len(rag_file_ids)} completed file(s) in conversation")

        # Add system instruction to guide tool usage
        # system_instruction = {
        #     "role": "system",
        #     "content": (
        #         f"You have access to {len(rag_file_ids)} uploaded and indexed PDF document(s). "
        #         "When the user asks questions about document content, specific information, "
        #         "or anything that would require reading the files, use the 'semantic_search' "
        #         "tool to retrieve relevant information from these documents. "
        #         "Do not guess or make up information - always search the documents first."
        #     )
        # }

        # Prepend system instruction to context
        # context_with_instruction = [system_instruction] + context_messages
        context_with_instruction = context_messages

        try:
            response_text, tool_call = send_chat_completion_with_tools(
                messages=context_with_instruction,
                tools=[SEMANTIC_SEARCH_TOOL]
            )
            
            if tool_call and tool_call["name"] == "semantic_search":
                # LLM decided to search!
                logger.info("LLM called semantic_search tool")
                
                # Extract search parameters
                query = tool_call["arguments"]["query"]
                top_k = tool_call["arguments"].get("top_k", 5)
                
                logger.info(f"Searching: query='{query[:50]}...', top_k={top_k}")
                
                # Generate embedding for query
                query_embedding = generate_embedding(query)
                
                # Search vector database (filtered by RAG files only)
                search_results = query_vectors(
                    query_vector=query_embedding,
                    top_k=top_k,
                    file_ids=rag_file_ids,  # Only search completed files!
                    include_metadata=True
                )
                
                logger.info(f"Retrieved {len(search_results)} chunks from vector DB")
                
                # Tool was called - always RAG mode (even if no results)
                retrieval_mode = RetrievalMode.RAG
                
                if search_results:
                    # Build context with retrieved chunks
                    context_with_chunks = build_context_with_retrieved_chunks(
                        original_messages=context_messages,
                        retrieved_chunks=search_results
                    )
                    
                    # Call LLM again with chunks
                    logger.info("Calling OpenAI with retrieved chunks")
                    assistant_response = send_chat_completion(context_with_chunks)
                    retrieved_chunks = _format_chunks_for_db(search_results)
                else:
                    # No results found, use direct response or inform user
                    logger.warning("No chunks retrieved from vector search")
                    assistant_response = response_text or "I couldn't find relevant information in the documents."
                    retrieved_chunks = []  # Empty list, not None
            else:
                # LLM responded directly (no tool call)
                logger.info("LLM responded directly without tool call")
                assistant_response = response_text
                retrieval_mode = RetrievalMode.INLINE
                
        except Exception as e:
            logger.error(f"RAG mode failed: {str(e)}")
            raise
    else:
        # Pure inline mode: No RAG files in conversation
        logger.info("Inline mode: No completed files in conversation")
        
        try:
            assistant_response = send_chat_completion(context_messages)
            retrieval_mode = RetrievalMode.INLINE
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    # Step 6: Save user message to database (only after OpenAI succeeds)
    logger.info("Saving user message to database")
    user_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=message_text,
        file_id=file_id
    )
    logger.debug(f"Saved user message: {user_message.id}")

    # Step 7: Save assistant response to database
    logger.info(f"Saving assistant response (mode: {retrieval_mode.value})")

    assistant_message = message_repo.create(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_response,
        retrieval_mode=retrieval_mode,
        retrieved_chunks=retrieved_chunks
    )
    logger.debug(f"Saved assistant message: {assistant_message.id}")

    # Step 8: Return response
    logger.info(
        f"Chat request completed: mode={retrieval_mode.value}, "
        f"chunks={len(retrieved_chunks)}"
    )
    return (
        conversation_id,
        assistant_response,
        retrieval_mode.value,
        retrieved_chunks
    )


def _append_historical_rag_chunks(
    context_messages: List[dict],
    db_messages: List[Message]
) -> List[dict]:
    """
    Append historical RAG chunks to context (Case 1).
    
    For assistant messages that used RAG mode, append their retrieved
    chunks as system messages right after the assistant message.
    
    Args:
        context_messages: Formatted messages from build_context_window
        db_messages: Original Message ORM objects from database
    
    Returns:
        Updated context messages with historical chunks appended
    """
    # Create a mapping of message content to retrieved chunks
    # (since we don't have message IDs in formatted messages)
    content_to_chunks = {}
    
    for db_msg in db_messages:
        if (
            db_msg.role == MessageRole.ASSISTANT and
            db_msg.retrieval_mode == RetrievalMode.RAG and
            db_msg.retrieved_chunks
        ):
            content_to_chunks[db_msg.content] = db_msg.retrieved_chunks
    
    if not content_to_chunks:
        logger.debug("No historical RAG chunks to append")
        return context_messages
    
    # Build new context with chunks inserted
    new_context = []
    chunks_added = 0
    
    for msg in context_messages:
        # Add the message
        new_context.append(msg)
        
        # If it's an assistant message with RAG chunks, add them
        if (
            msg.get("role") == "assistant" and
            msg.get("content") in content_to_chunks
        ):
            chunks = content_to_chunks[msg["content"]]
            
            # Format chunks as system message
            chunks_text_parts = ["Context used for this response:\n"]
            
            for idx, chunk in enumerate(chunks, 1):
                chunk_text = chunk.get("chunk_text", "")
                score = chunk.get("similarity_score", 0.0)
                
                if chunk_text:
                    chunks_text_parts.append(
                        f"\n[Chunk {idx}] (relevance: {score:.1%})\n{chunk_text}"
                    )
            
            chunks_content = "\n".join(chunks_text_parts)
            
            # Add as system message
            new_context.append({
                "role": "system",
                "content": chunks_content
            })
            
            chunks_added += 1
            logger.debug(
                f"Added {len(chunks)} historical chunks for assistant message"
            )
    
    if chunks_added > 0:
        logger.info(f"Appended historical RAG chunks for {chunks_added} message(s)")
    
    return new_context


def _format_chunks_for_db(search_results: List[dict]) -> list:
    """
    Format vector search results for database storage.
    
    Extracts relevant information from search results and formats
    for storage in the retrieved_chunks JSONB field.
    
    Args:
        search_results: List of results from query_vectors
    
    Returns:
        List of formatted chunk dictionaries for database
    """
    formatted_chunks = []
    
    for result in search_results:
        chunk_dict = {
            "chunk_text": result.get("metadata", {}).get("chunk_text", ""),
            "similarity_score": result.get("score", 0.0)
        }
        formatted_chunks.append(chunk_dict)
    
    return formatted_chunks
