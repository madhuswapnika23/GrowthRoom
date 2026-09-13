"""
Artifact-Generation Skill for Growth Room.

Generates structured artifacts (Markdown documents or self-contained HTML/CSS snippets)
based on conversation context and RAG insights.
Returns structured JSON output with a `type` field ("markdown" or "html")
so the frontend can route and render it correctly.
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

Your job is to generate self-contained artifacts (Markdown documents or standalone HTML/CSS components).

RULES:
1. OUTPUT FORMAT: You MUST return a JSON object with exactly two keys:
   - "type": string, either "markdown" or "html"
   - "content": string, the full content of the generated artifact
2. If "html" is requested or suitable, write clean, responsive HTML with inline CSS styling (or standard Tailwind/Vanilla flexbox styles) so it renders standalone.
3. If "markdown" is requested or suitable, write clean GitHub-flavored Markdown.
4. Ground all factual insights in the provided context when applicable.

Return ONLY the raw JSON object (no markdown fence wrapping, or inside ```json ... ``` codeblock)."""


class ArtifactGenSkill(AgentSkill):
    """Skill for generating structured Markdown or HTML artifacts."""

    @property
    def name(self) -> str:
        return "artifact_gen"

    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        logger.info("Executing ArtifactGenSkill for query: '%s'", query)

        # 1. Retrieve context
        retrieved_chunks: List[RetrievedChunk] = retrieve(query, db, top_k=3, min_score=0.20)
        
        context_str = ""
        sources_list: List[Dict[str, Any]] = []
        if retrieved_chunks:
            context_blocks = []
            for chunk in retrieved_chunks:
                context_blocks.append(f"Episode: {chunk.episode_title}\nText: {chunk.chunk_text}")
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

        # Determine requested type hint
        query_lower = query.lower()
        artifact_type_hint = "html" if ("html" in query_lower or "component" in query_lower or "dashboard" in query_lower or "ui" in query_lower) else "markdown"

        prompt = f"""KNOWLEDGE BASE CONTEXT:
{context_str or 'No specific transcript context provided.'}

USER REQUEST:
{query}

Generate a high-quality artifact (preferred type: {artifact_type_hint}).
Return JSON with "type" and "content" fields."""

        llm = get_llm_service()
        raw_output, provider_used = llm.generate(prompt, system=ARTIFACT_SYSTEM_PROMPT, temperature=0.2)

        # Parse JSON output from model
        artifact_data = None
        try:
            # Strip potential ```json markdown wrappers
            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
                cleaned = re.sub(r"\n```$", "", cleaned)
            
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
            logger.warning("Failed to parse JSON artifact output from model (%s). Wrapping output as markdown.", e)
            artifact_data = {
                "type": artifact_type_hint,
                "content": raw_output,
            }

        content_summary = f"Generated {artifact_data['type']} artifact based on user request:\n\n{artifact_data['content']}"

        return SkillResult(
            content=content_summary,
            sources=sources_list,
            grounding_score=float(avg_score),
            artifact=artifact_data,
            skill_name=self.name,
        )
