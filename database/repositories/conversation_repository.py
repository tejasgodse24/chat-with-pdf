"""
Conversation repository for database operations.
Handles all Conversation model database queries.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID

from database.models.conversation import Conversation


class ConversationRepository:
    """Repository for Conversation model database operations"""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self) -> Conversation:
        """
        Create a new conversation.

        Returns:
            Created Conversation object
        """
        db_conversation = Conversation()
        self.db.add(db_conversation)
        self.db.commit()
        self.db.refresh(db_conversation)
        return db_conversation

    def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """
        Get conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Conversation object or None if not found
        """
        return self.db.query(Conversation)\
            .filter(Conversation.id == conversation_id)\
            .first()

    def get_all_paginated(self, limit: int = 20, offset: int = 0) -> List[Conversation]:
        """
        Get paginated list of conversations, ordered by created_at descending.

        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List of Conversation objects
        """
        return self.db.query(Conversation)\
            .order_by(Conversation.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()

    def count_all(self) -> int:
        """
        Get total count of all conversations.

        Returns:
            Total number of conversations
        """
        return self.db.query(func.count(Conversation.id)).scalar()

    def delete(self, conversation_id: UUID) -> bool:
        """
        Delete conversation record (cascade deletes messages).

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if deleted, False if not found
        """
        db_conversation = self.get_by_id(conversation_id)
        if db_conversation:
            self.db.delete(db_conversation)
            self.db.commit()
            return True
        return False

    def exists(self, conversation_id: UUID) -> bool:
        """
        Check if conversation exists.

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if conversation exists, False otherwise
        """
        return self.db.query(Conversation.id)\
            .filter(Conversation.id == conversation_id)\
            .first() is not None
