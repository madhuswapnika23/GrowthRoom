# Growth Room — System Architecture

> This document describes the actual deployed system. All API shapes, DB columns, and pipeline steps are derived directly from the source code.

---

## 1. High-Level Topology

```
Browser (http://localhost:5173)
    │
    ▼
React / Vite (growthroom-frontend · port 5173)
    │  REST+JSON
    ▼
FastAPI (growthroom-backend · port 8000)
    │  SQLAlchemy / psycopg2
    ▼
PostgreSQL 16 + pgvector (growthroom-postgres · port 5432)

FastAPI ──► Anthropic API  (cloud, ANTHROPIC_API_KEY)
        └──► Ollama        (local, OLLAMA_BASE_URL:11434)
        └──► FallbackMock  (rule-based, always available)
```

---

## 2. Docker Compose Services

| Service | Image / Build | Port | Healthcheck |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | `5432` | `pg_isready` every 5 s, 10 retries |
| `backend` | `./backend/Dockerfile` (python:3.12-slim) | `8000` | `curl /health` every 10 s, 5 retries |
| `frontend` | `./frontend/Dockerfile` (node:20-alpine) | `5173` | `wget --spider http://127.0.0.1:5173` every 15 s |

**Dependency order:** `postgres` must be healthy before `backend` starts. `frontend` starts after `backend` (no healthcheck gate on backend readiness — Vite connects independently).

**Volume mounts (dev-only):**
- `./backend:/app` — live Python source sync; uvicorn runs with `--reload`.
- `postgres_data` named volume — persists DB across container restarts.

**Environment injection:** `backend` reads from `.env` via `env_file: .env`. All non-secret defaults are defined in `docker-compose.yml` environment overrides.

---

## 3. Database Schema (PostgreSQL 16)

Applied automatically from `db/migrations/` on first `postgres` container boot (mounted into `/docker-entrypoint-initdb.d/`).

### `sessions`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Session identifier |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `NOW()` | Session creation timestamp |
| `user_metadata` | `JSONB` | nullable | Reserved for future per-user context |

Index: `idx_sessions_created_at DESC` (drives session list ordering).

### `messages`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | Message identifier |
| `session_id` | `UUID` | FK → `sessions.id` ON DELETE CASCADE | Parent session |
| `role` | `ENUM('user','assistant','system')` | NOT NULL | Speaker identity |
| `content` | `TEXT` | NOT NULL | Raw message text |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Message timestamp |

Indexes: `idx_messages_session_id`, `idx_messages_created_at DESC`.

### `sources`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | Source record identifier |
| `message_id` | `UUID` | FK → `messages.id` ON DELETE CASCADE | Assistant message that cited this source |
| `episode_title` | `TEXT` | NOT NULL | Podcast episode title |
| `segment_timestamp` | `TEXT` | nullable | Chunk index label, e.g. `"Chunk 35"` |
| `relevance_score` | `FLOAT` | nullable | Cosine similarity score (0–1) |
| `source_url` | `TEXT` | nullable | YouTube URL from transcript frontmatter |

Index: `idx_sources_message_id`.

### `artifacts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | Artefact identifier |
| `message_id` | `UUID` | FK → `messages.id` ON DELETE CASCADE | Assistant message that produced this artefact |
| `type` | `ENUM('markdown','html')` | NOT NULL | Content format |
| `content` | `TEXT` | NOT NULL | Full artefact content |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Artefact creation timestamp |

Index: `idx_artifacts_message_id`.

### `kb_chunks`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | Chunk identifier |
| `episode_title` | `TEXT` | NOT NULL | Episode title from transcript frontmatter |
| `guest` | `TEXT` | nullable | Guest name from frontmatter |
| `youtube_url` | `TEXT` | nullable | YouTube link from frontmatter |
| `publish_date` | `DATE` | nullable | Publication date from frontmatter |
| `chunk_index` | `INT` | NOT NULL | Position within the episode (0-based) |
| `chunk_text` | `TEXT` | NOT NULL | Raw transcript text for this chunk |
| `token_count` | `INT` | nullable | tiktoken cl100k_base token count |
| `embedding` | `vector(384)` | NOT NULL | BAAI/bge-small-en-v1.5 embedding |
| `content_hash` | `TEXT` | NOT NULL, UNIQUE (via index) | MD5 of chunk content — prevents duplicate ingestion |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Ingest timestamp |

Unique index: `uq_kb_chunks_episode_chunk ON (episode_title, chunk_index)` — primary idempotency guard (used in `ON CONFLICT DO NOTHING`).

ANN index: `idx_kb_chunks_embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)` — enables sub-linear cosine similarity search. Falls back to sequential scan for < ~1,000 rows.

---

## 4. API Endpoints

All responses wrap data in `{ "status": "ok", "data": ... }`. Errors return `{ "error": { "code": "...", "message": "..." } }` with the appropriate HTTP status code.

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | API liveness. Returns `{ status, service, version }`. |
| `GET` | `/health/db` | — | PostgreSQL connectivity. Executes `SELECT 1`; returns 503 on failure. |
| `GET` | `/health/llm` | — | Checks whether `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` env var is set (not a live ping). |

### Sessions

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/sessions` | — | List of `SessionCard` objects: `session_id`, `title` (first user msg truncated to 60 chars), `created_at`, `message_count`, `artifact_count`, `latest_grounding_score` |
| `GET` | `/sessions/{session_id}` | Path param: UUID | Full session with ordered `messages` array; each message has `sources`, `artifact` (nullable) |
| `DELETE` | `/sessions/{session_id}` | Path param: UUID | `{ status, message }` — cascades to all child rows |

### Chat (Agent Execution)

**`POST /chat`**

Request:
```json
{
  "session_id": "uuid",     // optional — omit to create a new session
  "message": "string"       // required, min 1 character
}
```

Response:
```json
{
  "status": "ok",
  "data": {
    "session_id": "uuid",
    "message_id": "uuid",
    "content": "string",         // short chat summary; full essay/HTML is in artifact
    "skill_used": "grounded_qa | ship30 | artifact_gen",
    "grounding_score": 0.724,    // average chunk similarity score; 0.0 if no retrieval
    "sources": [
      {
        "episode_title": "string",
        "guest": "string | null",
        "segment_timestamp": "Chunk 35",
        "relevance_score": 0.724,
        "source_url": "https://youtube.com/..."
      }
    ],
    "artifact": {                // null for grounded_qa; present for ship30 / artifact_gen
      "type": "markdown | html",
      "content": "string"
    }
  }
}
```

### Model

| Method | Path | Request | Response |
|---|---|---|---|
| `GET` | `/model/status` | — | `{ configured_provider, active_provider, fallback_active, providers: { anthropic: {...}, ollama: {...}, fallback_mock: {...} } }` |
| `POST` | `/model/select` | `{ "provider": "anthropic" \| "ollama" \| "auto" }` | Updated status + confirmation message |

### Debug (dev only)

Enabled when `ENABLE_DEBUG_ENDPOINTS=true`. Mounted at `/debug/`. Used for knowledge-base diagnostics.

### OpenAPI

Interactive docs at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

---

## 5. Ingestion & Retrieval Pipeline

### 5.1 Ingestion (`app.ingestion`)

Run manually inside the backend container:
```bash
docker compose exec backend python -m app.ingestion.run
```

**Step-by-step:**

```
1. clone_or_pull()
   └─ If ./transcript_repo/.git exists: git pull --ff-only
   └─ Else: git clone --depth 1 https://github.com/ChatPRD/lennys-podcast-transcripts.git

2. load_transcripts()
   └─ Walks episodes/*/transcript.md files
   └─ Splits YAML frontmatter (---...---) from body text using yaml.safe_load
   └─ Extracts: episode_title, guest, youtube_url, publish_date
   └─ Yields TranscriptDoc objects (303 episodes in the current corpus)

3. chunk_text()  [chunker.py]
   └─ tiktoken cl100k_base encoding
   └─ max_tokens=512, overlap=64
   └─ Sentence-boundary snapping: finds last ". "/"? "/"! " past 50% of chunk
   └─ Falls back to hard token boundary if no sentence break found
   └─ Produces ~13,550 chunks total for 303 episodes

4. get_embedding_service().embed(batch)  [embedder.py]
   └─ FastEmbed / ONNX runtime — model: BAAI/bge-small-en-v1.5
   └─ 384-dimensional embeddings
   └─ No PyTorch required; runs on CPU in the Docker container
   └─ Batched in groups of 256 for memory efficiency

5. upsert_chunks()  [store.py]
   └─ For each chunk: computes MD5 content_hash
   └─ INSERT INTO kb_chunks ... ON CONFLICT (episode_title, chunk_index) DO NOTHING
   └─ Returns count of rows actually inserted (skips duplicates silently)
```

Re-running ingestion is safe and idempotent — duplicate chunks are silently skipped.

### 5.2 Retrieval (`app.retrieval.retriever`)

Called at request time by every skill:

```python
retrieve(query, db, top_k=5, min_score=0.20)
```

1. Embed the query string using the same FastEmbed model.
2. Execute pgvector cosine distance query:
   ```sql
   SELECT chunk_text, episode_title, guest, youtube_url, publish_date, chunk_index,
          1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
   FROM kb_chunks
   ORDER BY embedding <=> CAST(:query_embedding AS vector)
   LIMIT :top_k
   ```
3. Filter results: keep only rows where `similarity >= min_score`.
4. Return ordered list of `RetrievedChunk` dataclass instances.

**top_k by skill:**
- `grounded_qa`: top_k=5
- `ship30`: top_k=6 (more context for longer essay)
- `artifact_gen`: top_k=4

**Source traceability:** Every returned `RetrievedChunk` carries `episode_title`, `guest`, `youtube_url`, `chunk_index`, and `similarity_score`. These are persisted verbatim to the `sources` table and returned in the API response for frontend display.

---

## 6. Agent Routing Logic

Entry point: `POST /chat` → `AgentRouter.route_and_execute(query, history, db)`.

### Decision priority (checked in order)

**Priority 1 — Ship30 Triggers** (substring match, case-insensitive)

Matched phrases include: `"ship 30"`, `"ship30"`, `"atomic essay"`, `"write a post"`, `"write me a post"`, `"draft a post"`, `"draft an essay"`, `"write an essay"`, `"write me an essay"`, `"write an article"`, `"write me an article"`, `"create a post"`, `"create an essay"`, `"create an article"`, `"turn this into an essay"`, `"turn this into a post"`, `"thought leadership"`, `"newsletter"`.

→ Routes to `Ship30Skill`

**Priority 2 — Explicit Artefact Phrases** (substring match)

Matched phrases include: `"one-pager"`, `"onepager"`, `"one pager"`, `"landing page"`, `"landing-page"`, `"make me a page"`, `"make me a doc"`, `"make me a dashboard"`, `"make a one-pager"`, `"make a landing page"`, `"generate a doc"`, `"generate a page"`, `"generate a dashboard"`, `"create a doc"`, `"create a page"`, `"create a one-pager"`, `"build a page"`, `"build a dashboard"`, `"build a one-pager"`, `"turn this into a page"`, `"turn this into a dashboard"`, `"turn this into html"`, `"turn this into a doc"`, `"generate doc"`, `"create document"`, `"html snippet"`, `"build ui"`, `"create component"`, `"artifact"`, `"generate html"`, `"generate markdown"`, `"dashboard component"`, `"ui snippet"`, `"html code"`.

→ Routes to `ArtifactGenSkill`

**Priority 3 — Action + Target Combo**

If the query contains any action verb (`generate`, `create`, `build`, `make`, `design`) AND any target noun (`artifact`, `html`, `markdown`, `component`, `dashboard`, `ui`, `snippet`, `document`).

→ Routes to `ArtifactGenSkill`

**Priority 4 — Default**

Everything else.

→ Routes to `GroundedQASkill`

### Logging

Every routing decision emits a structured log line:
```
INFO  ROUTER_DECISION | skill='ship30' | reason='Ship30 trigger matched: "write an essay"' | query='Write a Ship 30 essay...'
INFO  SKILL_RESULT | skill='ship30' | grounding=0.612 | has_artifact=True | sources=6
```

---

## 7. LLM Provider Chain & Fallback

`LLMService` is a singleton (`get_llm_service()`). The chain is:

```
1. Primary provider (env LLM_PROVIDER, default: "anthropic")
   └─ AnthropicProvider.is_available()
      ├─ True → generate() → return (text, "anthropic")
      └─ False / exception → try secondary

2. Secondary provider (the other of anthropic/ollama)
   └─ OllamaProvider.is_available()  [HTTP GET /api/tags with 2s timeout]
      ├─ True → generate() → return (text, "ollama")
      └─ False / exception → try fallback

3. FallbackMockProvider (always available)
   └─ Rule-based synthesis from retrieved context embedded in the prompt
   └─ Returns (text, "fallback_mock")
```

**Runtime override:** `POST /model/select` updates `service.preferred_provider` on the singleton in-process without restart. Resets on container restart.

**Status polling:** `GET /model/status` returns `configured_provider`, `active_provider`, and `fallback_active` (true when active ≠ configured). The frontend Model tab polls this on mount.

---

## 8. Artefact Security

### HTML Artefact Isolation

All HTML produced by `ArtifactGenSkill` is rendered in a sandboxed iframe:

```jsx
<iframe
  srcDoc={artifact.content}
  sandbox=""           // empty string = all restrictions active
  style={{ width: '100%', height: '460px', border: 'none' }}
/>
```

**`sandbox=""` — what is blocked:**

| Capability | Status |
|---|---|
| Script execution (`<script>`, inline `onclick`, `eval`) | **BLOCKED** — `allow-scripts` not present |
| Same-origin access (localStorage, cookies, parent DOM) | **BLOCKED** — `allow-same-origin` not present |
| Form submission | **BLOCKED** — `allow-forms` not present |
| Top-level navigation | **BLOCKED** — `allow-top-navigation` not present |
| Popups / new windows | **BLOCKED** — `allow-popups` not present |
| CSS rendering | **ALLOWED** — CSS is not affected by sandbox |
| DOM element rendering | **ALLOWED** — HTML structure renders normally |

**`allow-scripts` is deliberately absent.** Even if the LLM generates `<script>` tags, they never execute. The `artifact_gen` system prompt also includes an explicit rule prohibiting `<script>` tags, providing defence in depth.

**`srcDoc` vs `src`:** Using `srcDoc` means the iframe content is injected from a JavaScript string — no HTTP request is made, so no `Content-Security-Policy` header negotiation is needed.

### Markdown Artefact Safety

Markdown is rendered via `react-markdown`, which never calls `dangerouslySetInnerHTML`. No raw HTML from the LLM is injected into the DOM.

---

## 9. Frontend Architecture

Stack: React 18, Vite 5, `react-markdown`.

Three top-level components composed in `App.jsx`:

| Component | Role |
|---|---|
| `SessionsRail` | Left panel: list, select, create, delete sessions |
| `ConversationLog` | Center panel: message feed, grounding meter, skill badge, input bar |
| `RightPanel` | Right panel: Artifact / Sources / Model tabs |

**State management:** All state lives in `App.jsx` (React `useState`). Components are purely presentational. No external state library.

**Optimistic updates:** User message appears in the chat immediately; rolled back on API error.

**Session restore:** On `GET /sessions/{id}`, the last assistant message's `sources` and `artifact` are extracted and loaded into the right panel. This means switching sessions correctly swaps both the chat and the right panel.

**Auto-tab switch:** When a response with a non-null `artifact` arrives, the right panel auto-switches to the Artifact tab. `useEffect` on the `artifact` prop also resets the raw/rendered toggle.
