"""
Message repository for database operations.
Handles all Message model database queries.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID

from database.models.message import Message, MessageRole, RetrievalMode


class MessageRepository:
    """Repository for Message model database operations"""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        file_id: Optional[UUID] = None,
        retrieval_mode: Optional[RetrievalMode] = None,
        retrieved_chunks: Optional[list] = None
    ) -> Message:
        """
        Create a new message.

        Args:
            conversation_id: UUID of the conversation
            role: Message role (user or assistant)
            content: Message text content
            file_id: Optional file UUID attached to this message
            retrieval_mode: Optional retrieval mode (inline or rag)
            retrieved_chunks: Optional list of retrieved chunks

        Returns:
            Created Message object
        """
        db_message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            file_id=file_id,
            retrieval_mode=retrieval_mode,
            retrieved_chunks=retrieved_chunks
        )
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        return db_message

    def get_by_id(self, message_id: UUID) -> Optional[Message]:
        """
        Get message by ID.

        Args:
            message_id: Message UUID

        Returns:
            Message object or None if not found
        """
        return self.db.query(Message)\
            .filter(Message.id == message_id)\
            .first()

    def get_by_conversation_id(
        self,
        conversation_id: UUID,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get all messages for a conversation, ordered by created_at ascending.

        Args:
            conversation_id: Conversation UUID
            limit: Optional limit on number of messages (for last N messages)

        Returns:
            List of Message objects ordered chronologically
        """
        query = self.db.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .order_by(Message.created_at.asc())

        if limit:
            # Get last N messages by reversing order, limiting, then re-reversing
            query = self.db.query(Message)\
                .filter(Message.conversation_id == conversation_id)\
                .order_by(Message.created_at.desc())\
                .limit(limit)\
                .from_self()\
                .order_by(Message.created_at.asc())

        return query.all()

    def count_by_conversation_id(self, conversation_id: UUID) -> int:
        """
        Get count of messages in a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Number of messages in the conversation
        """
        return self.db.query(func.count(Message.id))\
            .filter(Message.conversation_id == conversation_id)\
            .scalar()

    def delete(self, message_id: UUID) -> bool:
        """
        Delete message record.

        Args:
            message_id: Message UUID

        Returns:
            True if deleted, False if not found
        """
        db_message = self.get_by_id(message_id)
        if db_message:
            self.db.delete(db_message)
            self.db.commit()
            return True
        return False

    def delete_by_conversation_id(self, conversation_id: UUID) -> int:
        """
        Delete all messages in a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Number of messages deleted
        """
        count = self.db.query(Message)\
            .filter(Message.conversation_id == conversation_id)\
            .delete()
        self.db.commit()
        return count
