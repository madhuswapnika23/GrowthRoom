"""
Retriever — semantic search over the knowledge base using pgvector.

Given a query string, embeds it using the same model used at ingestion time,
then performs a cosine-similarity search over kb_chunks to return the top-K
most relevant chunks with their metadata and scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.ingestion.embedder import get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk returned by the retriever with similarity score."""
    chunk_text: str
    similarity_score: float
    episode_title: str
    guest: Optional[str]
    youtube_url: Optional[str]
    publish_date: Optional[date]
    chunk_index: int

    def to_dict(self) -> dict:
        return {
            "chunk_text": self.chunk_text,
            "similarity_score": round(self.similarity_score, 4),
            "episode_title": self.episode_title,
            "guest": self.guest,
            "youtube_url": self.youtube_url,
            "publish_date": str(self.publish_date) if self.publish_date else None,
            "chunk_index": self.chunk_index,
        }


def retrieve(
    query: str,
    db: Session,
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[RetrievedChunk]:
    """
    Retrieve the top-K most relevant chunks for a query.

    Uses pgvector's cosine distance operator (<=>).
    Cosine distance = 1 - cosine_similarity, so we convert:
      similarity = 1 - distance

    Args:
        query: The search query string.
        db: SQLAlchemy database session.
        top_k: Number of results to return.
        min_score: Minimum similarity score threshold (0-1).

    Returns:
        List of RetrievedChunk sorted by descending similarity.
    """
    embedder = get_embedding_service()
    query_embedding = embedder.embed_single(query)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = sql_text("""
        SELECT
            chunk_text,
            episode_title,
            guest,
            youtube_url,
            publish_date,
            chunk_index,
            1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
        FROM kb_chunks
        ORDER BY embedding <=> CAST(:query_embedding AS vector)
        LIMIT :top_k
    """)

    result = db.execute(
        sql,
        {"query_embedding": embedding_str, "top_k": top_k},
    )

    chunks = []
    for row in result:
        similarity = float(row.similarity)
        if similarity < min_score:
            continue
        chunks.append(
            RetrievedChunk(
                chunk_text=row.chunk_text,
                similarity_score=similarity,
                episode_title=row.episode_title,
                guest=row.guest,
                youtube_url=row.youtube_url,
                publish_date=row.publish_date,
                chunk_index=row.chunk_index,
            )
        )

    return chunks
