# Growth Room — System Architecture

## Overview

Growth Room is an AI-powered assistant that answers product and growth questions using knowledge from Lenny's Podcast transcripts. It uses a RAG (Retrieval-Augmented Generation) pipeline to find relevant transcript segments and ground responses in real source material.

## Services & Component Boundaries

| Component | Responsibility | Technology |
|---|---|---|
| **API Layer** | Exposes HTTP routes; handles sessions; invokes router. | FastAPI / Python (Port 8000) |
| **Agent Layer** | Heuristic routing; Skill execution; LLM Provider (Fallback) management. | Python (`app.agent.*`) |
| **Ingestion Pipeline** | Pulls GitHub transcripts; chunks tokens; generates ONNX embeddings; inserts hashes. | Python (`app.ingestion.*`) |
| **Database** | Persistent state for vector RAG, historic conversations, and artifacts. | PostgreSQL 16 + pgvector (Port 5432) |
| **Frontend UI** | Three-surface React application (Rails, Log, Tabs). | React / Vite (Port 5173) |

---

## Database Schema (PostgreSQL)

The persistence layer organizes conversation tracking and vector storage.

### `sessions`
- `id` (UUID, PK)
- `created_at` (TIMESTAMPTZ)
- `user_metadata` (JSONB)

### `messages`
- `id` (UUID, PK)
- `session_id` (UUID, FK -> sessions.id)
- `role` (ENUM: 'user', 'assistant', 'system')
- `content` (TEXT)
- `created_at` (TIMESTAMPTZ)

### `sources`
- `id` (UUID, PK)
- `message_id` (UUID, FK -> messages.id)
- `episode_title` (VARCHAR 500)
- `segment_timestamp` (VARCHAR 50)
- `relevance_score` (FLOAT)
- `source_url` (TEXT)

### `artifacts`
- `id` (UUID, PK)
- `message_id` (UUID, FK -> messages.id)
- `type` (ENUM: 'markdown', 'html')
- `content` (TEXT)
- `created_at` (TIMESTAMPTZ)

### `kb_chunks` (pgvector Data)
- `id` (UUID, PK)
- `episode_title` (TEXT)
- `guest` (TEXT)
- `youtube_url` (TEXT)
- `publish_date` (TIMESTAMP)
- `chunk_index` (INTEGER)
- `chunk_text` (TEXT)
- `token_count` (INTEGER)
- `content_hash` (TEXT, UNIQUE) — *Allows idempotent upserts*
- `embedding` (VECTOR(384)) — *IVFFlat index on `vector_cosine_ops`*
- `created_at` (TIMESTAMPTZ)

---

## API Endpoints (Contracts)

### Session Management

**`GET /sessions`**
- **Purpose**: Lists all historic sessions with metadata required for the left-rail UI.
- **Request**: None.
- **Response Shape:**
  ```json
  {
    "status": "ok",
    "data": [
      {
        "session_id": "uuid",
        "title": "Truncated first user msg...",
        "created_at": "ISO-8601",
        "message_count": 4,
        "artifact_count": 1,
        "latest_grounding_score": 0.94
      }
    ]
  }
  ```

**`GET /sessions/{session_id}`**
- **Purpose**: Fetches the detailed conversation log (messages, sources, artifacts) for the center/right UI panels.
- **Request Parameters**: `session_id` (UUID).
- **Response Shape:**
  ```json
  {
    "status": "ok",
    "data": {
      "session_id": "uuid",
      "created_at": "ISO-8601",
      "messages": [
        {
          "id": "uuid",
          "role": "user | assistant",
          "content": "Message text",
          "created_at": "ISO-8601",
          "sources": [...],
          "artifact": {"type": "markdown", "content": "..."} // Optional
        }
      ]
    }
  }
  ```

**`DELETE /sessions/{session_id}`**
- **Purpose**: Hard deletes a session (cascades to messages, sources, artifacts).

### Agent Execution

**`POST /chat`**
- **Purpose**: Main entry point for user prompts, kicking off Agent routing, DB parsing, and LLM inference.
- **Request Shape:**
  ```json
  {
    "session_id": "uuid", // Optional (creates new if omitted)
    "message": "What is a retention loop?"
  }
  ```
- **Response Shape:** Same envelope mapping to `GET /sessions/{session_id}`.

### Model Toggles

**`GET /model/status`**
- **Purpose**: Retrieve the active LLM provider and network fallback statuses.
- **Response Shape:**
  ```json
  {
    "status": "ok",
    "data": {
      "configured_provider": "anthropic",
      "active_provider": "ollama",
      "fallback_active": true,
      "providers": {
        "anthropic": {"available": false},
        "ollama": {"available": true, "model": "llama3.2:3b"}
      }
    }
  }
  ```

**`POST /model/select`**
- **Purpose**: Manually override the active provider via the frontend UI.
- **Request Shape:**
  ```json
  { "provider": "anthropic" | "ollama" | "auto" }
  ```

---

## Agent Routing & Flow

User queries are triaged instantly using heuristic-based matching (`app.agent.router`).
1. **Rule Match (`ship30`)**: Keywords such as `"ship 30", "essay", "post", "atomic essay"`.
2. **Rule Match (`artifact_gen`)**: Keywords such as `"generate doc", "html", "ui", "artifact"`.
3. **Default (`grounded_qa`)**: The fallback handler for standard product/growth Q&A.

**Flow:**
`POST /chat` ➞ Retrieve Session DB ➞ Invoke Router ➞ Initialize Skill (e.g., `grounded_qa`) ➞ Query PgVector (Top 8 chunks) ➞ Infer LLM ➞ Parse Output ➞ Persist DB ➞ Return to Web UI.

---

## Ingestion Pipeline

1. **Git Pull**: Shallow clones [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts).
2. **YAML Parsing**: Extracts frontmatter (guest, title, youtube URL, publish date).
3. **Token Window Chunking**: Splits MD files using `tiktoken` (cl100k_base). Max 512 tokens, 64-token overlap, intelligently breaking on sentence boundaries (`.`/`?`/`!`).
4. **ONNX Embedding**: Uses `BAAI/bge-small-en-v1.5` via `fastembed` (no PyTorch dependencies required; extremely fast inference on laptops).
5. **Idempotent Upsert**: Computes an MD5 hash of chunk metadata+content. Connects to Postgres; issues a `INSERT ... ON CONFLICT (content_hash) DO NOTHING` command to allow robust re-running of ingestion.

---

## Model Toggle Mechanism

The `LLMService` wrapper intercepts every model call.
If `LLM_PROVIDER=anthropic`, it attempts the Anthropic Claude API.
If Claude timeouts/fails (e.g. no internet), `LLMService` automatically swallows the error, logs a graceful fallback warning, and executes via local `Ollama` running on port 11434. 
If Ollama is *also* dead, it executes a `FallbackMockProvider` rule-based string output.

The UI polls `GET /model/status` to determine the truth state of this cascade.

---

## Artifact Security (HTML Sandboxing)

The `artifact_gen` skill is capable of producing arbitrary HTML, CSS, and JS components based on LLM hallucinations.
**Security Rule:** To prevent XSS vulnerabilities, the React frontend isolates generated HTML inside an explicitly constrained `<iframe>`.

**Implementation:**
```html
<iframe srcDoc={artifact.content} sandbox="" />
```
- **`sandbox=""`**: Applying an empty string strictly enforces *all* sandbox restrictions natively built into major browsers.
- **Allowed**: Safe rendering of DOM structural elements and inline CSS.
- **Blocked**: Everything else. `allow-scripts` is specifically omitted, neutralizing `<script>` injection. `allow-same-origin` is omitted, isolating the frame from accessing user storage (localStorage, cookies). Top-level navigation is denied.
