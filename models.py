"""
SQLAlchemy models for Telegram Secretary Bot.
Defines Message and UserPreferences tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
# PostgreSQL ARRAY removed for SQLite compatibility
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Message(Base):
    """
    Stores all captured Telegram messages with metadata.
    Used for filtering, scoring, and ML training data collection.
    """
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Telegram identifiers
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chat_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # private, group, supergroup, channel
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Message content
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Metadata flags
    has_mention: Mapped[bool] = mapped_column(Boolean, default=False)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    message_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # AI-generated topic summary (3 words)
    topic_summary: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Scoring and labeling
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # high, medium, low
    labeled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Tracking
    included_in_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    warning_sent: Mapped[bool] = mapped_column(Boolean, default=False)  # Real-time warning sent
    warning_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=func.now(),
        server_default=func.now()
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_messages_label", "label"),
        Index("idx_messages_timestamp", "timestamp"),
        Index("idx_messages_chat_id", "chat_id"),
        Index("idx_messages_user_id", "user_id"),
        Index("idx_messages_included_summary", "included_in_summary"),
        # Composite index for summary queries
        Index("idx_messages_unlabeled_recent", "label", "timestamp", "included_in_summary"),
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, chat={self.chat_id}, user={self.user_id})>"


class UserPreferences(Base):
    """
    Stores user-specific preferences for the secretary bot.
    Currently designed for single user but extensible for multi-user.
    """
    __tablename__ = "user_preferences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    
    # Summary preferences
    summary_interval_hours: Mapped[int] = mapped_column(Integer, default=4)
    max_messages_per_summary: Mapped[int] = mapped_column(Integer, default=15)
    
    # Filtering preferences (stored as JSON string for SQLite compatibility)
    excluded_chat_ids_json: Mapped[Optional[str]] = mapped_column(
        Text, 
        default="[]",
        nullable=True
    )
    
    # Quiet hours (don't send summaries during this time)
    quiet_hours_start: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        return f"<UserPreferences(user_id={self.user_id})>"


class HighPriorityUser(Base):
    """
    Stores users marked as high priority.
    Messages from these users get +2 score boost.
    """
    __tablename__ = "high_priority_users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_high_priority_user_id", "user_id"),
    )
    
    def __repr__(self) -> str:
        return f"<HighPriorityUser(user_id={self.user_id})>"

