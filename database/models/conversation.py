"""
Conversation model for tracking chat sessions.
"""
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from .base import Base


class Conversation(Base):
    """
    Conversation model representing chat sessions.

    Attributes:
        id: Unique conversation identifier (UUID)
        created_at: Timestamp when conversation was started
        messages: Relationship to Message model (one-to-many)
    """
    __tablename__ = "conversations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique conversation identifier"
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when conversation was started"
    )

    # Relationship to messages (one conversation has many messages)
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, created_at={self.created_at})>"
