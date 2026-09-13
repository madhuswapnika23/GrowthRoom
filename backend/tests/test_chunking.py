"""
Tests for the chunking logic.
"""

from app.ingestion.chunker import chunk_text


class TestChunking:
    """Tests for chunk_text function."""

    def test_chunks_within_token_limit(self):
        """All chunks should be at or below the max_tokens limit."""
        # Create a moderately long text (~2000 tokens worth)
        text = "This is a test sentence about product management and growth. " * 200
        max_tokens = 512

        chunks = chunk_text(text, max_tokens=max_tokens, overlap=64)

        assert len(chunks) > 1, "Long text should produce multiple chunks"
        for chunk in chunks:
            assert chunk.token_count <= max_tokens + 10, (
                f"Chunk {chunk.chunk_index} has {chunk.token_count} tokens, "
                f"exceeds limit of {max_tokens}"
            )

    def test_chunks_have_overlap(self):
        """Adjacent chunks should share some overlapping text."""
        text = "This is a test sentence about product management strategies. " * 200
        chunks = chunk_text(text, max_tokens=100, overlap=20)

        assert len(chunks) >= 3, "Should produce several chunks"

        # Check that at least some adjacent pairs share text
        overlap_found = False
        for i in range(len(chunks) - 1):
            # Get the tail of the current chunk and head of the next
            tail = chunks[i].text[-100:]  # last 100 chars
            head = chunks[i + 1].text[:100]  # first 100 chars
            # Check for any shared words
            tail_words = set(tail.split())
            head_words = set(head.split())
            if tail_words & head_words:
                overlap_found = True
                break

        assert overlap_found, "Adjacent chunks should share some overlapping text"

    def test_short_text_single_chunk(self):
        """A short text should produce exactly one chunk."""
        text = "Product-market fit is the key to startup success."
        chunks = chunk_text(text, max_tokens=512, overlap=64)

        assert len(chunks) == 1, "Short text should be a single chunk"
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == text

    def test_empty_text_no_chunks(self):
        """Empty text should produce no chunks."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_indices_are_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        text = "Growth metrics and retention rates matter. " * 150
        chunks = chunk_text(text, max_tokens=100, overlap=20)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i, (
                f"Expected chunk_index {i}, got {chunk.chunk_index}"
            )

    def test_all_text_covered(self):
        """All significant content from the original text should appear in chunks."""
        text = "Alpha bravo charlie delta echo foxtrot. " * 100
        chunks = chunk_text(text, max_tokens=100, overlap=20)

        combined = " ".join(c.text for c in chunks)
        # Check that key words from the original appear in combined chunks
        for word in ["Alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]:
            assert word in combined, f"Word '{word}' missing from chunks"
