"""
Dependency injection for FastAPI routes.
Provides repository instances and other dependencies.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from database.models.base import get_db
from database.repositories import FileRepository, ConversationRepository, MessageRepository


def get_file_repository(db: Session = Depends(get_db)) -> FileRepository:
    """
    Dependency to provide FileRepository instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        FileRepository instance

    Usage:
        @router.get("/files")
        async def list_files(file_repo: FileRepository = Depends(get_file_repository)):
            files = file_repo.get_all_paginated()
    """
    return FileRepository(db)


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    """
    Dependency to provide ConversationRepository instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        ConversationRepository instance

    Usage:
        @router.post("/chat")
        async def chat(conv_repo: ConversationRepository = Depends(get_conversation_repository)):
            conversation = conv_repo.create()
    """
    return ConversationRepository(db)


def get_message_repository(db: Session = Depends(get_db)) -> MessageRepository:
    """
    Dependency to provide MessageRepository instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        MessageRepository instance

    Usage:
        @router.post("/chat")
        async def chat(msg_repo: MessageRepository = Depends(get_message_repository)):
            messages = msg_repo.get_by_conversation_id(conv_id)
    """
    return MessageRepository(db)
