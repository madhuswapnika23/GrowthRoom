"""
Chunk store — idempotent upsert of chunks + embeddings into Postgres.

Uses content_hash (SHA-256 of chunk_text) and a unique constraint on
(episode_title, chunk_index) to support re-ingestion without duplicates.
Changed content is re-embedded and updated in place.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    """Data ready to be upserted into kb_chunks."""
    episode_title: str
    guest: Optional[str]
    youtube_url: Optional[str]
    publish_date: Optional[date]
    chunk_index: int
    chunk_text: str
    token_count: int
    embedding: list[float]


def _content_hash(text: str) -> str:
    """SHA-256 hash of chunk text for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_chunks(db: Session, chunks: list[ChunkRecord]) -> int:
    """
    Bulk upsert chunk records into kb_chunks.
    Returns the number of rows affected (inserted + updated).

    Uses ON CONFLICT (episode_title, chunk_index) DO UPDATE
    to support idempotent re-ingestion.
    """
    if not chunks:
        return 0

    upsert_sql = sql_text("""
        INSERT INTO kb_chunks (
            episode_title, guest, youtube_url, publish_date,
            chunk_index, chunk_text, token_count, embedding, content_hash
        ) VALUES (
            :p_episode_title, :p_guest, :p_youtube_url, :p_publish_date,
            :p_chunk_index, :p_chunk_text, :p_token_count,
            CAST(:p_embedding AS vector), :p_content_hash
        )
        ON CONFLICT (episode_title, chunk_index) DO UPDATE SET
            guest = EXCLUDED.guest,
            youtube_url = EXCLUDED.youtube_url,
            publish_date = EXCLUDED.publish_date,
            chunk_text = EXCLUDED.chunk_text,
            token_count = EXCLUDED.token_count,
            embedding = EXCLUDED.embedding,
            content_hash = EXCLUDED.content_hash
        WHERE kb_chunks.content_hash != EXCLUDED.content_hash
    """)

    affected = 0
    # Process in batches of 100 to avoid huge transactions
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        for chunk in batch:
            content_hash = _content_hash(chunk.chunk_text)
            embedding_str = "[" + ",".join(str(v) for v in chunk.embedding) + "]"
            result = db.execute(
                upsert_sql,
                {
                    "p_episode_title": chunk.episode_title,
                    "p_guest": chunk.guest,
                    "p_youtube_url": chunk.youtube_url,
                    "p_publish_date": chunk.publish_date,
                    "p_chunk_index": chunk.chunk_index,
                    "p_chunk_text": chunk.chunk_text,
                    "p_token_count": chunk.token_count,
                    "p_embedding": embedding_str,
                    "p_content_hash": content_hash,
                },
            )
            affected += result.rowcount
        db.commit()

    return affected


def delete_episode_chunks(db: Session, episode_title: str) -> int:
    """Delete all chunks for a specific episode. Returns rows deleted."""
    result = db.execute(
        sql_text("DELETE FROM kb_chunks WHERE episode_title = :title"),
        {"title": episode_title},
    )
    db.commit()
    return result.rowcount


def get_chunk_count(db: Session) -> int:
    """Get total number of chunks in the knowledge base."""
    result = db.execute(sql_text("SELECT COUNT(*) FROM kb_chunks"))
    return result.scalar() or 0
