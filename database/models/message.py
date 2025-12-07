"""
Message model for storing chat messages.
"""
from sqlalchemy import Column, String, DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from .base import Base
from enum import Enum


class MessageRole(str, Enum):
    """Enum for message roles"""
    USER = "user"
    ASSISTANT = "assistant"


class RetrievalMode(str, Enum):
    """Enum for retrieval modes"""
    INLINE = "inline"
    RAG = "rag"


class Message(Base):
    """
    Message model representing individual messages in a conversation.

    Attributes:
        id: Unique message identifier (UUID)
        conversation_id: Foreign key to conversation
        role: Who sent the message (user or assistant)
        content: Message text content
        file_id: Optional reference to PDF file attached to this message
        retrieval_mode: How assistant retrieved information (inline or rag)
        retrieved_chunks: JSON array of chunks used for RAG (null for inline)
        created_at: Timestamp when message was sent
    """
    __tablename__ = "messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique message identifier"
    )

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to conversation"
    )

    role = Column(
        SAEnum(MessageRole, name="message_role_enum"),
        nullable=False,
        comment="Message role: user or assistant"
    )

    content = Column(
        Text,
        nullable=False,
        comment="Message text content"
    )

    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to PDF file attached to this message"
    )

    retrieval_mode = Column(
        SAEnum(RetrievalMode, name="retrieval_mode_enum"),
        nullable=True,
        comment="How assistant retrieved information (null for user messages)"
    )

    retrieved_chunks = Column(
        JSONB,
        nullable=True,
        comment="JSON array of retrieved chunks (null for inline or user messages)"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when message was sent"
    )

    # Relationships
    conversation = relationship(
        "Conversation",
        back_populates="messages"
    )

    file = relationship(
        "File",
        foreign_keys=[file_id]
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
