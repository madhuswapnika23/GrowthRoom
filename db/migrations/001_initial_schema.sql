-- =============================================================================
-- Migration 001: Initial schema for Growth Room
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- ENUMs
-- ---------------------------------------------------------------------------

CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE artifact_type AS ENUM ('markdown', 'html');

-- ---------------------------------------------------------------------------
-- sessions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at    TIMESTAMPTZ NOT NULL    DEFAULT NOW(),
    user_metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at DESC);

-- ---------------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS messages (
    id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID          NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role       message_role  NOT NULL,
    content    TEXT          NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id  ON messages (session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at  ON messages (created_at DESC);

-- ---------------------------------------------------------------------------
-- sources  (cited podcast segments)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sources (
    id                UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id        UUID    NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    episode_title     TEXT    NOT NULL,
    segment_timestamp TEXT,                          -- e.g. "01:23:45"
    relevance_score   FLOAT,
    source_url        TEXT
);

CREATE INDEX IF NOT EXISTS idx_sources_message_id ON sources (message_id);

-- ---------------------------------------------------------------------------
-- artifacts  (generated markdown / html content)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS artifacts (
    id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID          NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    type       artifact_type NOT NULL,
    content    TEXT          NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_message_id ON artifacts (message_id);
