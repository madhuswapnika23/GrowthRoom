# Agent Development & Implementation Log

## Overview
This log documents the architecture, skill routing design, provider fallback cascade, and key development iterations for **The Lenny Growth Assistant** (Growth Room).

---

## 1. Agent Architecture & Routing

The agent layer uses a **heuristic router** (`app/agent/router.py`) to triage incoming user prompts into specialized skills:
- `ship30`: Selected when user prompts contain keywords like `"ship 30"`, `"ship30"`, `"essay"`, or `"atomic essay"`.
- `artifact_gen`: Selected when prompts request structured content, HTML snippets, components, dashboards, or UI mockups.
- `grounded_qa`: Default skill for analytical and factual Q&A grounded strictly in transcript vector search (`pgvector`).

### Skill Execution Flow
```
User Prompt → AgentRouter → Select Skill (ship30 / artifact_gen / grounded_qa)
                                   ↓
                         Retrieve Top-K Chunks (pgvector)
                                   ↓
                         Evaluate Grounding Confidence (<0.35 threshold)
                                   ↓
                         LLM Service (Anthropic → Ollama → FallbackMock)
                                   ↓
                         Return SkillResult (Content + Sources + Grounding Score + Artifact)
```

---

## 2. Iterations & Bug Resolutions

### Issue 1: Runtime Preferred Provider Override State
- **Symptom:** Switching providers via the UI (`POST /model/select`) set `service.preferred_provider`, but `LLMService` in `app/agent/llm.py` was ignoring instance state and strictly reading environment variables.
- **Resolution:** Updated `LLMService.__init__` to initialize `self.preferred_provider` and modified `_get_preferred_provider_name()` and `get_status()` to read the instance property.

### Issue 2: Frontend Radio Button Binding
- **Symptom:** In `RightPanel.jsx`, the `Auto` radio button had `checked={... || true}`, visually locking the override UI to "Auto" regardless of user selection.
- **Resolution:** Fixed radio button `checked` bindings to dynamically match `statusData.configured_provider`.

### Issue 3: Offline / Fallback Synthesis Enhancement
- **Symptom:** When neither Anthropic API Key nor local Ollama was connected, `FallbackMockProvider` returned a static 1-sentence placeholder string for every query.
- **Resolution:** Enhanced `FallbackMockProvider.generate()` to extract episode titles, guest names, and transcript sentences from retrieved context, dynamically synthesizing structured Grounded QA answers, Ship 30 essays (Hook -> Insight -> Principles -> Actionable Takeaway), and sandboxed HTML UI artifacts.

---

## 3. Grounding & Security Constraints

1. **Hallucination Prevention:** If vector search yields 0 chunks or maximum similarity < 0.35, `GroundedQASkill` returns an explicit *"I don't have enough source material in the knowledge base..."* response instead of hallucinating.
2. **HTML Sandboxing:** All generated HTML artifacts render inside an `<iframe>` with strict `sandbox=""` attributes, preventing script execution, cookie access, or top-level navigation.
