"""
Tests for retrieval — known-query returns expected top result.

These tests require a running Postgres with pgvector and data loaded.
They use the real embedding model and database.
"""

import os
import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from app.ingestion.embedder import get_embedding_service
from app.ingestion.store import ChunkRecord, upsert_chunks
from app.retrieval.retriever import retrieve


def _get_test_db():
    """Get a test database session."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://growthroom:changeme_dev@localhost:5432/growthroom",
    )
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    return Session()


# Unique test prefix to avoid collision with real data
_TEST_PREFIX = "__TEST_RETRIEVAL__"


@pytest.fixture(scope="module")
def db_with_test_data():
    """
    Insert known test chunks and yield a DB session.
    Cleans up after tests.
    """
    db = _get_test_db()

    # Ensure pgvector extension exists
    db.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()

    embedder = get_embedding_service()

    test_chunks_data = [
        {
            "episode_title": f"{_TEST_PREFIX} Product-Market Fit Deep Dive",
            "guest": "Test Guest PMF",
            "youtube_url": "https://youtube.com/test-pmf",
            "chunk_text": (
                "Product-market fit is the degree to which a product satisfies "
                "a strong market demand. It's the moment when your product "
                "resonates with customers and they can't imagine going back. "
                "The key indicators are retention, word of mouth, and organic growth."
            ),
        },
        {
            "episode_title": f"{_TEST_PREFIX} Growth Strategy Masterclass",
            "guest": "Test Guest Growth",
            "youtube_url": "https://youtube.com/test-growth",
            "chunk_text": (
                "Growth strategy involves identifying the key levers that drive "
                "user acquisition, activation, retention, and monetization. "
                "The AARRR framework is fundamental. Focus on the metric that "
                "matters most for your stage."
            ),
        },
        {
            "episode_title": f"{_TEST_PREFIX} Engineering Leadership",
            "guest": "Test Guest Eng",
            "youtube_url": "https://youtube.com/test-eng",
            "chunk_text": (
                "Cooking a perfect soufflé requires patience and precise "
                "temperature control. The eggs must be at room temperature "
                "and the oven preheated to exactly 375 degrees Fahrenheit."
            ),
        },
    ]

    # Generate embeddings
    texts = [c["chunk_text"] for c in test_chunks_data]
    embeddings = embedder.embed(texts)

    records = []
    for i, (chunk_data, emb) in enumerate(zip(test_chunks_data, embeddings)):
        records.append(
            ChunkRecord(
                episode_title=chunk_data["episode_title"],
                guest=chunk_data["guest"],
                youtube_url=chunk_data["youtube_url"],
                publish_date=None,
                chunk_index=0,
                chunk_text=chunk_data["chunk_text"],
                token_count=len(chunk_data["chunk_text"].split()),
                embedding=emb,
            )
        )

    upsert_chunks(db, records)

    yield db

    # Cleanup: delete test chunks
    db.execute(
        sql_text("DELETE FROM kb_chunks WHERE episode_title LIKE :prefix"),
        {"prefix": f"{_TEST_PREFIX}%"},
    )
    db.commit()
    db.close()


class TestRetrieval:
    """Tests for the retrieval function with known test data."""

    def test_known_query_returns_expected_result(self, db_with_test_data):
        """
        Querying 'product-market fit' should return the PMF chunk as the top result
        with a high similarity score.
        """
        db = db_with_test_data
        results = retrieve("What is product-market fit?", db=db, top_k=5)

        assert len(results) > 0, "Should return at least one result"

        # The top result should be the PMF chunk
        top = results[0]
        assert _TEST_PREFIX in top.episode_title, "Top result should be a test chunk"
        assert "product-market fit" in top.chunk_text.lower() or "Product-Market Fit" in top.episode_title
        assert top.similarity_score > 0.5, (
            f"Expected high similarity score, got {top.similarity_score}"
        )

        pass
