# Growth Room

Growth Room is an internal AI assistant that answers product and growth questions using *Lenny's Podcast* transcripts. It uses retrieval-augmented generation (RAG) to ground every answer in real transcript excerpts, and refuses to answer when the knowledge base lacks relevant evidence.

---

## Architecture Overview

```
Browser (http://localhost:5173)
    │
    ▼
React / Vite — frontend
    │  REST + JSON
    ▼
FastAPI — backend (Port 8000)
    │  SQLAlchemy
    ▼
PostgreSQL 16 + pgvector (Port 5432)

Backend also calls:
  → Anthropic API  (cloud LLM)
  → Ollama         (local LLM, optional)
  → FallbackMock   (rule-based, always available)
```

Three Docker Compose services start in dependency order: `postgres` → `backend` → `frontend`. All healthchecks are defined; the backend won't start until the database passes `pg_isready`.

See **[docs/architecture.md](docs/architecture.md)** for the full schema, all API endpoint shapes, ingestion pipeline details, router logic, and artefact security documentation.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Docker Engine | ≥ 24 |
| Docker Compose | v2 (`docker compose`, not `docker-compose`) |
| Available RAM | ≥ 4 GB (pgvector + ONNX embedding model during ingestion) |
| LLM provider | Anthropic API key **or** Ollama running locally (see below) |

No local Python, Node, or PostgreSQL installation needed — everything runs inside Docker.

---

## Install & Run

### 1. Clone the repository

```bash
git clone <repo-url>
cd "oogway project"
```

### 2. Configure environment

```bash
# On Linux / macOS
cp .env.example .env

# On Windows PowerShell
Copy-Item .env.example .env
```

Edit `.env` and fill in your LLM credentials (see [Environment Variables](#environment-variables) below).

### 3. Start the application

```bash
docker compose up -d --build
```

This command:
- Builds the backend (Python 3.12 + dependencies) and frontend (Node 20 + Vite) images.
- Starts `postgres`, waits for it to be healthy.
- Starts `backend`, waits for `/health` to return 200.
- Starts `frontend`.

First build takes 2–5 minutes (downloads base images and Python/npm dependencies). Subsequent builds are faster due to layer caching.

### 4. Verify services are running

```bash
docker compose ps
```

All three containers should show `Up` with `(healthy)` status.

Check API health:
```bash
# Linux / macOS
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/model/status

# Windows PowerShell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
Invoke-RestMethod http://localhost:8000/model/status
```

### 5. Load the knowledge base

The application needs transcript chunks in the database before it can answer questions. Run the ingestion pipeline inside the backend container:

```bash
docker compose exec backend python -m app.ingestion.run
```

This:
1. Clones the [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts) repository (303 episodes).
2. Chunks each transcript (512-token windows, 64-token overlap).
3. Generates embeddings using `BAAI/bge-small-en-v1.5` via FastEmbed/ONNX (downloads model on first run, ~67 MB).
4. Upserts ~13,550 chunks into PostgreSQL.

Ingestion is idempotent — re-running it is safe and will skip already-inserted chunks.

### 6. Open the application

Navigate to **[http://localhost:5173](http://localhost:5173)**.

---

## Environment Variables

All variables are defined in `.env` (copied from `.env.example`). The backend reads this file via Docker Compose `env_file`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_DB` | Yes | `growthroom` | PostgreSQL database name |
| `POSTGRES_USER` | Yes | `growthroom` | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | `changeme_dev` | PostgreSQL password — change for any shared environment |
| `DATABASE_URL` | Yes | See `.env.example` | SQLAlchemy connection string. Must match `POSTGRES_*` values. |
| `API_HOST` | No | `0.0.0.0` | Uvicorn bind host |
| `API_PORT` | No | `8000` | Uvicorn port |
| `API_RELOAD` | No | `true` | Enable uvicorn `--reload` (hot-reload in dev) |
| `LOG_LEVEL` | No | `info` | Python logging level (`debug`, `info`, `warning`, `error`) |
| `LLM_PROVIDER` | No | `anthropic` | Primary LLM provider: `anthropic` or `ollama` |
| `ANTHROPIC_API_KEY` | Cond. | `sk-ant-replace-me` | Required if `LLM_PROVIDER=anthropic`. Get from [console.anthropic.com](https://console.anthropic.com). |
| `ANTHROPIC_MODEL` | No | `claude-3-5-sonnet-20241022` | Anthropic model name |
| `OLLAMA_BASE_URL` | Cond. | `http://localhost:11434` | Required if `LLM_PROVIDER=ollama`. Use `http://host.docker.internal:11434` on Docker Desktop (Windows/macOS). |
| `OLLAMA_MODEL` | No | `llama3.2:3b` | Ollama model to use |
| `EMBEDDING_MODEL` | No | `BAAI/bge-small-en-v1.5` | FastEmbed model for ingestion and retrieval. Do not change after ingestion without re-ingesting. |
| `ENABLE_DEBUG_ENDPOINTS` | No | `true` | Mounts `/debug/` routes for knowledge-base diagnostics |
| `TRANSCRIPT_REPO_URL` | No | See `.env.example` | GitHub URL of the transcript repository |
| `TRANSCRIPT_REPO_PATH` | No | `./transcript_repo` | Local path inside the container where the repo is cloned |
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Backend URL used by the Vite frontend at build time |

### Setting up Anthropic (cloud)

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### Setting up Ollama (local)

1. Install Ollama from [ollama.com](https://ollama.com) and pull the model:

```bash
ollama run llama3.2:3b
```

2. In `.env`:

```env
LLM_PROVIDER=ollama
# Docker Desktop on Windows or macOS:
OLLAMA_BASE_URL=http://host.docker.internal:11434
# Linux with host network:
OLLAMA_BASE_URL=http://172.17.0.1:11434
OLLAMA_MODEL=llama3.2:3b
```

3. Restart the backend: `docker compose restart backend`

### Running without any LLM key

Leave both `ANTHROPIC_API_KEY` and `OLLAMA_BASE_URL` as their placeholder values. The system will use `FallbackMockProvider` — a rule-based synthesiser that composes answers from retrieved transcript context without calling an external LLM. The Model tab will show "Fallback Active" in amber.

---

## Running the Test Suite

```bash
docker compose exec backend python -m pytest tests/ -v
```

Tests cover:
- API contract tests (`tests/test_router.py`, `tests/test_api_persistence.py`)
- Retrieval behaviour (`tests/test_retrieval.py`, `tests/test_retrieval_empty.py`)
- Model provider toggle (`tests/test_model_toggle.py`)
- Grounded Q&A pipeline (`tests/test_grounded_qa.py`)
- Chunking logic (`tests/test_chunking.py`)

Tests use an in-memory SQLite database (via test fixtures) — no live PostgreSQL connection is required to run the suite.

Rebuild a single service if dependencies change:

```bash
docker compose up -d --build backend
docker compose up -d --build frontend
```

---

## Troubleshooting

### "Answers say there is not enough source material"

The knowledge base is empty. Run ingestion:

```bash
docker compose exec backend python -m app.ingestion.run
```

Then verify the database is populated:

```bash
# Linux / macOS
curl http://localhost:8000/health/db

# Windows PowerShell
Invoke-RestMethod http://localhost:8000/health/db
```

If `ENABLE_DEBUG_ENDPOINTS=true`, you can also query the debug API at `http://localhost:8000/debug/`.

### "The backend cannot reach Anthropic or Ollama"

Check `GET /model/status` or the Model tab in the UI. The `fallback_active` field shows whether the system has fallen back to rule-based synthesis.

For Anthropic: verify `ANTHROPIC_API_KEY` in `.env` is not the placeholder `sk-ant-replace-me`.

For Ollama: confirm the model is running (`ollama list`), then confirm the URL is reachable from inside the Docker container:

```bash
docker compose exec backend curl http://host.docker.internal:11434/api/tags
```

Restart the backend after changing `.env`:

```bash
docker compose restart backend
```

### "The database needs to be reset"

The migration scripts in `db/migrations/` run automatically only when the PostgreSQL data volume is first created. To recreate it:

```bash
docker compose down -v          # destroys the volume
docker compose up -d --build    # recreates from scratch
```

Then re-run ingestion.

### "Docker build fails with API 500 error"

This is a Docker daemon error, not a code error. Restart Docker Desktop and try again. The backend source files are volume-mounted (`./backend:/app`) and uvicorn runs with `--reload`, so most Python code changes are picked up automatically without a rebuild.

### "The frontend is blank / shows a network error"

Verify the backend is healthy before the frontend makes requests:

```bash
docker compose ps
# All three containers should show (healthy)
```

If the backend shows `unhealthy`, view its logs:

```bash
docker compose logs backend
```

Common causes: missing `.env` file, database not yet healthy, or Python import error from a code change.

### "Port already in use"

Stop any existing containers first:

```bash
docker compose down
```

If another process is using port 8000 or 5173, find and stop it, or change the port mapping in `docker-compose.yml`.

---

## Stopping the Application

```bash
docker compose down           # stops containers, preserves database volume
docker compose down -v        # stops containers AND deletes database (full reset)
```

---

## Repository Layout

```
backend/              FastAPI application, agent skills, retrieval, ingestion, tests
  app/
    agent/            Router, skills (grounded_qa, ship30, artifact_gen), LLM providers
    api/              HTTP endpoints (chat, sessions, health, model_status, debug)
    db/               SQLAlchemy models, session factory
    ingestion/        Pipeline (loader, chunker, embedder, store, run)
    retrieval/        retriever.py — pgvector cosine search
  tests/              pytest test suite
db/migrations/        SQL migration files (auto-applied on first DB boot)
docs/                 PRD, architecture, design, QA documentation
frontend/             React + Vite application
  src/
    components/       ConversationLog, RightPanel, SessionsRail
    App.jsx           Root component and global state
    index.css         Design system (CSS custom properties + all styles)
docker-compose.yml    Local development stack definition
.env.example          Environment variable template
```

---

## Documentation

- [Product Requirements Document](docs/PRD.md)
- [System Architecture](docs/architecture.md)
- [Frontend Design](docs/design.md)
- [QA Guide](docs/QA.md)
- [Interactive API docs (when running)](http://localhost:8000/docs)
