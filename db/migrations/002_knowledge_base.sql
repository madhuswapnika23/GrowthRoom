-- =============================================================================
-- Migration 002: Knowledge-base chunks with pgvector embeddings
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- kb_chunks — stores chunked transcript segments with embeddings
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kb_chunks (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_title TEXT        NOT NULL,
    guest         TEXT,
    youtube_url   TEXT,
    publish_date  DATE,
    chunk_index   INT         NOT NULL,
    chunk_text    TEXT        NOT NULL,
    token_count   INT,
    embedding     vector(384) NOT NULL,
    content_hash  TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint for idempotent re-ingestion
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_chunks_episode_chunk
    ON kb_chunks (episode_title, chunk_index);

-- IVFFlat index for fast cosine-similarity search
-- NOTE: IVFFlat requires data to be present before building.
-- On first ingestion with few rows, Postgres will use sequential scan.
-- After bulk insert, run: REINDEX INDEX idx_kb_chunks_embedding;
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
    ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index for filtering by episode
CREATE INDEX IF NOT EXISTS idx_kb_chunks_episode_title
    ON kb_chunks (episode_title);
