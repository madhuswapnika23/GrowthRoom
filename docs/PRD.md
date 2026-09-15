# Growth Room — Product Requirements Document

> **Scope note:** This document describes the system as actually built and deployed. It does not describe aspirational features.

---

## 1. Primary User & Job-to-Be-Done

**Primary user:** Product Managers, Growth Engineers, and early-stage Founders who consume strategy content from *Lenny's Podcast* and need to apply it to live decisions.

**Job-to-be-done:**
> When I am working through a product or growth problem — building a retention loop, finding product-market fit signals, choosing a GTM motion — I want to instantly query the collective tactical knowledge of every *Lenny's Podcast* guest, so I can apply proven frameworks without spending hours scrubbing audio or reading SEO-optimised summaries.

Three sub-jobs the system addresses:

| Sub-job | Skill invoked |
|---|---|
| Look up a specific fact or framework | `grounded_qa` |
| Turn a topic into a publishable short-form essay | `ship30` |
| Generate a structured artefact (one-pager, dashboard) | `artifact_gen` |

---

## 2. Measurable Success Metrics

**Metric 1 — Citation coverage (primary)**
Target: ≥ 80 % of `grounded_qa` responses return ≥ 1 cited source with `relevance_score ≥ 0.35`.
Measured by: the `grounding_score` field on each `POST /chat` response (average of chunk similarity scores for the retrieved context). If retrieval scores fall below threshold the system refuses to answer rather than fabricate.

**Metric 2 — Artefact generation success rate**
Target: ≥ 90 % of `ship30` and `artifact_gen` requests return a non-empty `artifact.content` that is parseable (valid Markdown or valid HTML with at least one HTML element).
Measured by: checking the `artifact` field in the chat response envelope is non-null with `content` length > 100 characters.

**Metric 3 — Median time-to-grounded-answer**
Target: < 10 s from `POST /chat` request to full JSON response (using `fallback_mock` provider as baseline; real LLM latency is provider-dependent).
Measured by: end-to-end timing instrumentation in the chat endpoint request/response cycle.

---

## 3. Assumptions Made Due to Incomplete Brief

| Assumption | Implication |
|---|---|
| Single-tenant / internal deployment — no user auth required | Authentication and multi-tenancy are explicitly out of scope for v1. |
| The *Lenny's Podcast* transcript GitHub repo is the sole authorised knowledge source | The system bans outside-knowledge answers; if retrieval returns nothing above threshold, it says so. |
| The evaluator has Docker ≥ 24 and Docker Compose v2 installed | The entire stack is Compose-only; no Makefile, no bare-Python setup path is documented. |
| A developer will set a real `ANTHROPIC_API_KEY` or run Ollama locally | The system degrades gracefully to `FallbackMockProvider` (rule-based synthesis) if neither is available; the Model tab shows the current state. |
| 512-token fixed-window chunking adequately segments podcast transcripts | Transcripts lack speaker turn annotations; fixed windows with 64-token overlap were chosen as a robust default. |

---

## 4. Scope

### Included

- **Grounded Q&A (RAG):** Cosine similarity search over pgvector knowledge base, strict context-only synthesis, numeric grounding score returned to frontend.
- **Ship 30 for 30 essay skill:** Full essay (hook → core insight → 3-4 sourced lessons → single actionable takeaway) generated and stored as a `markdown` artefact, grounded in retrieved transcript chunks.
- **Artefact-generation skill:** Produces `markdown` (one-pager, brief, notes) or `html` (dashboard component, landing page) artefacts stored in the database and rendered in the frontend panel.
- **Agent router:** Heuristic phrase-matching router that selects among the three skills and logs the decision with a structured `ROUTER_DECISION` log line.
- **Three-skill LLM provider chain:** Anthropic → Ollama → FallbackMockProvider with automatic cascade on failure.
- **Runtime provider override:** `POST /model/select` allows switching providers without restarting the backend.
- **Persistent sessions:** All messages, sources, and artefacts are persisted to PostgreSQL; past sessions are fully restorable.
- **Sandboxed artefact viewer:** HTML artefacts rendered in `<iframe sandbox="">` (strictest mode — no scripts, no same-origin); Markdown rendered via `react-markdown`.
- **Raw/Rendered toggle:** Both HTML and Markdown artefacts support toggling between rendered view and raw source.
- **Knowledge-base ingestion pipeline:** Git-clone → YAML frontmatter parsing → tiktoken chunking (512 tokens, 64 overlap) → FastEmbed ONNX embeddings (BAAI/bge-small-en-v1.5) → idempotent upsert into PostgreSQL/pgvector.
- **Full Docker Compose stack:** Three services (postgres, backend, frontend) with healthchecks and auto-restart.

### Explicitly Excluded

| Exclusion | Reason |
|---|---|
| Audio / video playback | YouTube links with chunk timestamps are sufficient; embedding players adds complexity for no analytical value. |
| Multi-tenant authentication / user accounts | Not required for internal single-tenant v1. |
| Semantic re-ranking (cross-encoders, Cohere Rerank) | Adds external API dependency; pgvector cosine similarity is adequate for the dataset size. |
| Streaming LLM responses | Simplifies the response contract; full response is suitable for the artefact-oriented UX. |
| Fine-tuning or few-shot prompt caching | Out of scope; all grounding comes from RAG, not model adaptation. |
| PDF export of artefacts | Users can use the browser print dialog; programmatic PDF export deferred to v2. |

---

## 5. Risks & Trade-offs

| Risk | Likelihood | Mitigation / Trade-off |
|---|---|---|
| **Hallucination** | Medium | Strict system prompts enforce context-only answers. `CONFIDENCE_THRESHOLD = 0.35` — if no chunk scores above this, the system returns an explicit "not enough source material" message instead of guessing. |
| **Latency** | Medium | Retrieval embeds the query (ONNX, ~5–15 ms), runs a pgvector ANN search, and then calls the LLM synchronously. For Anthropic Claude 3.5 Sonnet, total round-trip is typically 3–8 s. Ship30/artifact_gen calls with longer prompts can reach 10–20 s. |
| **Ollama quality ceiling** | High | `llama3.2:3b` (the default local model) produces adequate grounded Q&A but generates lower-quality HTML artefacts compared to Claude 3.5 Sonnet. This is documented and the provider toggle is surfaced in the UI. |
| **Cost** | Low | Anthropic API calls with ~3,000-token prompts (context + query) cost approximately $0.003–$0.008 per request at Claude 3.5 Sonnet pricing. No streaming means no partial-response waste. |
| **Data leakage** | Low | PostgreSQL runs inside the Docker network. Transcript text reaches Anthropic's API only when the Anthropic provider is active. No user PII is collected. |
| **Unsafe artefact rendering** | Low | `<iframe sandbox="">` blocks scripts, same-origin access, form submission, and top-navigation. Even if the LLM generates `<script>` tags, they are inert. The system prompt for `artifact_gen` also explicitly prohibits `<script>` tags. |
| **Ingestion idempotency** | Low | The unique index on `(episode_title, chunk_index)` does `ON CONFLICT DO NOTHING`. Re-running ingestion against an already-populated database is safe. |

---

## 6. User Flows & Acceptance Criteria

### Flow 1 — Factual Q&A

1. User opens `http://localhost:5173`.
2. User types a product question (e.g. *"How do top PMs design retention loops?"*).
3. Router logs `ROUTER_DECISION | skill='grounded_qa'`.
4. Retriever fetches top-5 chunks from `kb_chunks` (cosine similarity, min_score=0.20).
5. LLM synthesises an answer strictly from the retrieved context.
6. Response includes `grounding_score`, an array of `sources`, and `artifact: null`.
7. Frontend shows: grounding meter (colored by score), answer in Markdown, source chips in the Sources tab.

**Acceptance criteria:**
- [ ] Response contains `skill_used: "grounded_qa"`.
- [ ] `sources` array is non-empty for questions answerable from the knowledge base.
- [ ] If `grounding_score < 0.35`, response content is the "not enough source material" message (no hallucinated answer).
- [ ] Sources tab shows episode title, chunk reference, relevance score, and YouTube link.

### Flow 2 — Ship 30 Essay

1. User types *"Write a Ship 30 essay on finding product-market fit"*.
2. Router logs `ROUTER_DECISION | skill='ship30'` (matched trigger: `"write"` + `"essay"`… actually matched: `"write an essay"` substring).
3. Retriever fetches top-6 chunks.
4. LLM produces a full essay (~800–1,250 words) following the Ship 30 arc: hook → core problem → 3-4 sourced lessons → one actionable takeaway.
5. Chat message shows a brief confirmation pointing to the Artifact panel.
6. Artifact panel auto-activates and renders the essay via `react-markdown`.
7. Sources tab lists all chunks cited.

**Acceptance criteria:**
- [ ] Response contains `skill_used: "ship30"`.
- [ ] `artifact.type == "markdown"` and `artifact.content` length > 500 characters.
- [ ] Chat panel shows skill badge "✍️ Ship 30 Essay".
- [ ] Artifact panel auto-selects when response arrives.
- [ ] Raw/Rendered toggle works for the markdown artefact.
- [ ] Session reload restores the essay in the Artifact panel.

### Flow 3 — HTML Artefact Generation

1. User types *"Generate an HTML snippet for a SaaS growth metrics dashboard"*.
2. Router logs `ROUTER_DECISION | skill='artifact_gen'` (matched `artifact_action + artifact_target` combo).
3. Retriever fetches top-4 chunks for grounding context.
4. LLM returns a JSON object `{ "type": "html", "content": "..." }`.
5. Artefact is stored in the `artifacts` table and returned in the chat response.
6. Artifact panel renders the HTML in `<iframe sandbox="">`.
7. User can toggle to raw source view.

**Acceptance criteria:**
- [ ] Response contains `skill_used: "artifact_gen"`.
- [ ] `artifact.type == "html"` and content contains `<` and `>` (valid HTML).
- [ ] iframe renders without console errors.
- [ ] `sandbox=""` attribute is present on the iframe (no `allow-scripts`).
- [ ] Download button produces a `.html` file.

### Flow 4 — Provider Fallback

1. No valid `ANTHROPIC_API_KEY` is set (placeholder value).
2. Ollama is not running.
3. User sends a query.
4. `LLMService` tries Anthropic (fails — placeholder key), tries Ollama (fails — not running), falls back to `FallbackMockProvider`.
5. Model tab shows "Fallback Active" pill in amber.
6. Response is still returned (rule-based synthesis from retrieved context).

**Acceptance criteria:**
- [ ] `GET /model/status` returns `fallback_active: true` when no real provider is reachable.
- [ ] Model tab pill colour is amber.
- [ ] Chat still receives a response (not a 500 error).

---

## 7. Decision-to-Rubric Mapping

| Key Decision | Rubric Dimension |
|---|---|
| Defined a strict JTBD (internal research tool, not general chatbot) and scope-limited to prevent feature creep | Customer & Product Judgment |
| Grounding score exposed in the API response and rendered visually in the UI — refuses to answer when below threshold rather than hallucinating | Customer & Product Judgment |
| Router, Skill, LLM, DB, API layers are strictly bounded; no cross-layer imports outside defined interfaces | Technical Execution & Code Quality |
| Idempotent ingestion via `ON CONFLICT DO NOTHING` lets re-ingestion run safely at any time | Technical Execution |
| Heuristic router with phrase-priority list (Ship30 checked before ArtifactGen checked before GroundedQA) + structured `ROUTER_DECISION` log line | Agentic Architecture & Grounding |
| Each skill retrieves from the same `retrieve()` function — grounding is not skill-specific, it's a shared primitive | Agentic Architecture & Grounding |
| Single `docker compose up -d --build` brings up all three services with correct dependency order and healthchecks | Deployment & Operability |
| `/health`, `/health/db`, `/model/status` endpoints enable external monitoring | Deployment & Operability |
| Type hints throughout (`from __future__ import annotations`), Pydantic schemas for all API contracts, `@dataclass` for internal data types | Code Quality |
| Three-surface layout (sessions / chat / artefact+sources) keeps the conversation readable while surfacing deep content in dedicated tabs | UI/UX Quality |
| `<iframe sandbox="">` with explicit security comment in source; JSON output contract documented in system prompts and architecture doc | Communication |
