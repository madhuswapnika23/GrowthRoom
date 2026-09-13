"""
SQLAlchemy ORM models for Growth Room.

Tables:
  - sessions   : conversation sessions per user
  - messages   : individual chat turns within a session
  - sources    : podcast segments cited in a message
  - artifacts  : generated content (markdown / html) attached to a message
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    user_metadata = Column(JSONB, nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        Enum("user", "assistant", "system", name="message_role"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    session = relationship("Session", back_populates="messages")
    sources = relationship("Source", back_populates="message", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="message", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Source (cited podcast segment)
# ---------------------------------------------------------------------------

class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    episode_title = Column(String(500), nullable=False)
    segment_timestamp = Column(String(50), nullable=True)   # e.g. "01:23:45"
    relevance_score = Column(Float, nullable=True)
    source_url = Column(Text, nullable=True)

    message = relationship("Message", back_populates="sources")


# ---------------------------------------------------------------------------
# Artifact (generated content)
# ---------------------------------------------------------------------------

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    type = Column(
        Enum("markdown", "html", name="artifact_type"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    message = relationship("Message", back_populates="artifacts")


# ---------------------------------------------------------------------------
# KBChunk (knowledge-base chunk with embedding)
# ---------------------------------------------------------------------------

class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_title = Column(Text, nullable=False)
    guest = Column(Text, nullable=True)
    youtube_url = Column(Text, nullable=True)
    publish_date = Column(DateTime, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(384), nullable=False)
    content_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

