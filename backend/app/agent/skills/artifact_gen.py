"""
Artifact-Generation Skill for Growth Room.

Generates structured artifacts (Markdown documents or self-contained HTML/CSS snippets)
based on conversation context and RAG insights.

Output contract:
  - content  : short human-readable confirmation for the chat panel
  - artifact : { type: "markdown" | "html", content: <full generated content> }
  - sources  : retrieved transcript chunks used for grounding
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.agent.llm import get_llm_service
from app.agent.skills.base import AgentSkill, SkillResult
from app.retrieval.retriever import retrieve, RetrievedChunk

logger = logging.getLogger(__name__)

ARTIFACT_SYSTEM_PROMPT = """You are Growth Room's specialized Artifact Generator.

Your job is to generate self-contained artifacts grounded in Lenny's Podcast knowledge.

OUTPUT CONTRACT (CRITICAL):
Return a SINGLE valid JSON object with exactly two keys:
  {
    "type": "html" | "markdown",
    "content": "<the complete artifact content as a string>"
  }

Do NOT wrap the JSON in markdown code fences (no ```json ... ```).
Do NOT return anything before or after the JSON object.

CONTENT RULES:
1. If "html" type: write clean, self-contained HTML with inline CSS. Must render standalone. Use a dark professional theme by default.
2. If "markdown" type: write clean GitHub-Flavored Markdown with clear headers, bullets, and bold emphasis.
3. Ground factual insights in the provided transcript context when available.
4. HTML artifacts must not include <script> tags -- CSS-only styling only.
5. Produce genuinely useful, dense content -- not a skeleton."""


class ArtifactGenSkill(AgentSkill):
    """Skill for generating structured Markdown or HTML artifacts."""

    @property
    def name(self) -> str:
        return "artifact_gen"

    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        logger.info("Executing ArtifactGenSkill for query: '%s'", query)

        # 1. Retrieve context
        retrieved_chunks: List[RetrievedChunk] = retrieve(query, db, top_k=4, min_score=0.20)

        context_str = ""
        sources_list: List[Dict[str, Any]] = []
        if retrieved_chunks:
            context_blocks = []
            for idx, chunk in enumerate(retrieved_chunks, start=1):
                guest_str = f" ({chunk.guest})" if chunk.guest else ""
                context_blocks.append(
                    f"--- Source {idx}: {chunk.episode_title}{guest_str} ---\n{chunk.chunk_text}"
                )
                sources_list.append({
                    "episode_title": chunk.episode_title,
                    "guest": chunk.guest,
                    "segment_timestamp": f"Chunk {chunk.chunk_index}",
                    "relevance_score": round(chunk.similarity_score, 4),
                    "source_url": chunk.youtube_url,
                })
            context_str = "\n\n".join(context_blocks)

        scores = [c.similarity_score for c in retrieved_chunks] if retrieved_chunks else [0.0]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Determine requested artifact type from user request
        query_lower = query.lower()
        if any(kw in query_lower for kw in ("html", "component", "dashboard", "ui", "page", "landing", "one-pager", "onepager")):
            artifact_type_hint = "html"
        else:
            artifact_type_hint = "markdown"

        prompt = f"""KNOWLEDGE BASE CONTEXT:
{context_str or 'No specific transcript context available -- use general product/growth principles.'}

USER REQUEST:
{query}

Generate a high-quality {artifact_type_hint} artifact.
Return a single JSON object with "type" and "content" keys as specified.
Do NOT include markdown code fences around the JSON."""

        llm = get_llm_service()
        raw_output, provider_used = llm.generate(prompt, system=ARTIFACT_SYSTEM_PROMPT, temperature=0.2)

        logger.info("ArtifactGenSkill raw output length: %d chars, provider: %s", len(raw_output), provider_used)

        # Parse JSON output from model
        artifact_data = None
        try:
            cleaned = raw_output.strip()
            # Strip potential ```json markdown wrappers the model may include
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned.rstrip())
            # Handle cases where the model prefixes explanation before JSON
            json_start = cleaned.find("{")
            if json_start > 0:
                cleaned = cleaned[json_start:]

            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "type" in parsed and "content" in parsed:
                artifact_type = str(parsed["type"]).lower()
                if artifact_type not in ("markdown", "html"):
                    artifact_type = artifact_type_hint
                artifact_data = {
                    "type": artifact_type,
                    "content": str(parsed["content"]),
                }
        except Exception as e:
            logger.warning("Failed to parse JSON artifact output (%s). Wrapping as %s.", e, artifact_type_hint)
            artifact_data = {
                "type": artifact_type_hint,
                "content": raw_output,
            }

        art_type = artifact_data["type"]
        logger.info(
            "ArtifactGenSkill produced: type=%s, content_length=%d, sources=%d",
            art_type, len(artifact_data["content"]), len(sources_list),
        )

        # Short confirmation for the chat panel
        source_note = f" grounded in {len(sources_list)} transcript sources" if sources_list else ""
        chat_summary = (
            f"**{art_type.upper()} artifact generated**{source_note}. "
            f"View it rendered in the **Artifact panel** on the right."
        )

        return SkillResult(
            content=chat_summary,
            sources=sources_list,
            grounding_score=float(avg_score),
            artifact=artifact_data,
            skill_name=self.name,
        )
