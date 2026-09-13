"""
Tests for the empty/no-good-match retrieval case.

Verifies that the retriever returns low scores or no results
when querying for something completely unrelated to the knowledge base.
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


_TEST_PREFIX = "__TEST_EMPTY__"


@pytest.fixture(scope="module")
def db_with_narrow_data():
    """
    Insert a small, specific dataset so we can test unrelated queries.
    """
    db = _get_test_db()

    db.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()

    embedder = get_embedding_service()

    # Only product-related chunks
    test_text = (
        "Product-market fit is when customers love your product so much "
        "they tell others about it. Key metrics include NPS, retention rate, "
        "and organic referral growth."
    )

    embedding = embedder.embed_single(test_text)

    records = [
        ChunkRecord(
            episode_title=f"{_TEST_PREFIX} PMF Episode",
            guest="Test Guest",
            youtube_url="https://youtube.com/test",
            publish_date=None,
            chunk_index=0,
            chunk_text=test_text,
            token_count=len(test_text.split()),
            embedding=embedding,
        )
    ]

    upsert_chunks(db, records)
    yield db

    # Cleanup
    db.execute(
        sql_text("DELETE FROM kb_chunks WHERE episode_title LIKE :prefix"),
        {"prefix": f"{_TEST_PREFIX}%"},
    )
    db.commit()
    db.close()


class TestRetrievalEmpty:
    """Tests for no-match / low-score retrieval scenarios."""

    def test_unrelated_query_returns_low_scores(self, db_with_narrow_data):
        """
        Querying for something completely unrelated (e.g., quantum physics)
        should return results with low similarity scores.
        """
        db = db_with_narrow_data
        results = retrieve(
            "Explain quantum entanglement and wave function collapse",
            db=db,
            top_k=5,
        )

        # If results are returned, their scores should be low
        for r in results:
            if _TEST_PREFIX in r.episode_title:
                assert r.similarity_score < 0.5, (
                    f"Unrelated query should have low score, got {r.similarity_score} "
                    f"for chunk: {r.chunk_text[:50]}..."
                )

    def test_min_score_filter_works(self, db_with_narrow_data):
        """
        Using a high min_score threshold should filter out weak matches.
        """
        db = db_with_narrow_data
        results = retrieve(
            "Explain quantum entanglement and wave function collapse",
            db=db,
            top_k=5,
            min_score=0.8,
        )

        # With a 0.8 threshold, unrelated queries should return few or no results
        test_results = [r for r in results if _TEST_PREFIX in r.episode_title]
        assert len(test_results) == 0, (
            f"High min_score should filter out weak matches, "
            f"got {len(test_results)} results"
        )

    def test_relevant_query_scores_higher_than_irrelevant(self, db_with_narrow_data):
        """
        A relevant query should score meaningfully higher than an irrelevant one.
        """
        db = db_with_narrow_data

        relevant = retrieve("product-market fit retention", db=db, top_k=1)
        irrelevant = retrieve("quantum physics dark matter antimatter", db=db, top_k=1)

        # Filter to test chunks only
        rel_test = [r for r in relevant if _TEST_PREFIX in r.episode_title]
        irr_test = [r for r in irrelevant if _TEST_PREFIX in r.episode_title]

        if rel_test and irr_test:
            assert rel_test[0].similarity_score > irr_test[0].similarity_score, (
                f"Relevant query ({rel_test[0].similarity_score}) should score "
                f"higher than irrelevant ({irr_test[0].similarity_score})"
            )
