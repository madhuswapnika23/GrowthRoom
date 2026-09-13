"""
Ship 30 for 30 Skill for Growth Room.

Encodes core Ship 30 for 30 essay principles:
  1. Strong Hook: Grab attention immediately in line 1.
  2. Skimmable Formatting: Short paragraphs, headers (##), bullet points, bold key terms.
  3. Narrative Progression: Clear structure (Hook -> Core Insight -> Key Principles/Steps -> 1 Actionable Takeaway).
  4. Single Actionable Takeaway: Exactly one clear thing the reader can do today.
  5. Strict RAG Grounding: All core claims sourced exclusively from retrieved podcast transcripts.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.agent.llm import get_llm_service
from app.agent.skills.base import AgentSkill, SkillResult
from app.retrieval.retriever import retrieve, RetrievedChunk

logger = logging.getLogger(__name__)

SHIP30_SYSTEM_PROMPT = """You are a master digital writer trained in the Ship 30 for 30 writing methodology.

Your goal is to transform the provided podcast knowledge base insights into a high-impact, skimmable Atomic Essay / Thought Leadership Post.

SHIP 30 FOR 30 WRITING RULES:
1. HOOK: Start with a strong 1-2 line hook that grabs attention (bold statement, counter-intuitive truth, or provocative question). No fluff or filler intros.
2. SKIMMABLE FORMATTING:
   - Use descriptive headers (`## Section Title`).
   - Keep paragraphs short (1-3 sentences max).
   - Use bullet points and **bold text** for key concepts.
3. NARRATIVE PROGRESSION:
   - Hook
   - The Core Problem / Insight
   - 3-4 Key Lessons / Principles (grounded in the context)
   - One Specific Actionable Takeaway
4. SINGLE ACTIONABLE TAKEAWAY: End with exactly ONE concrete action step the reader can execute immediately.
5. STRICT GROUNDING: Use ONLY the provided transcript context for all factual claims, quotes, and guest insights. Do NOT invent facts.
6. TARGET WORD COUNT: Write a comprehensive, well-developed post (~800-1200 words if context allows)."""


class Ship30Skill(AgentSkill):
    """Skill for generating Ship 30 for 30 style structured essays / posts grounded in RAG."""

    @property
    def name(self) -> str:
        return "ship30"

    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        logger.info("Executing Ship30Skill for query: '%s'", query)

        # 1. Retrieve relevant podcast transcript chunks
        retrieved_chunks: List[RetrievedChunk] = retrieve(query, db, top_k=5, min_score=0.20)

        if not retrieved_chunks:
            return SkillResult(
                content="I don't have enough source material in the knowledge base to write a grounded Ship 30 essay on this topic.",
                sources=[],
                grounding_score=0.0,
                artifact=None,
                skill_name=self.name,
            )

        scores = [c.similarity_score for c in retrieved_chunks]
        avg_score = sum(scores) / len(scores)

        # 2. Build context and sources list
        context_blocks = []
        sources_list: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(retrieved_chunks, start=1):
            guest_str = f" ({chunk.guest})" if chunk.guest else ""
            context_blocks.append(f"--- Chunk {idx} ({chunk.episode_title}{guest_str}) ---\n{chunk.chunk_text}")

            sources_list.append({
                "episode_title": chunk.episode_title,
                "guest": chunk.guest,
                "segment_timestamp": f"Chunk {chunk.chunk_index}",
                "relevance_score": round(chunk.similarity_score, 4),
                "source_url": chunk.youtube_url,
            })

        context_str = "\n\n".join(context_blocks)

        prompt = f"""KNOWLEDGE BASE CONTEXT:
{context_str}

USER REQUEST:
{query}

Write a high-converting, Ship 30 for 30 style essay / post grounded in the knowledge base context above.
Follow all Ship 30 rules (Strong Hook, Skimmable Formatting, Narrative Progression, One Actionable Takeaway, Strict Grounding)."""

        # 3. Generate essay
        llm = get_llm_service()
        essay_content, provider_used = llm.generate(prompt, system=SHIP30_SYSTEM_PROMPT, temperature=0.3)

        # Create a Markdown artifact for the essay
        artifact_data = {
            "type": "markdown",
            "content": essay_content,
        }

        return SkillResult(
            content=essay_content,
            sources=sources_list,
            grounding_score=float(avg_score),
            artifact=artifact_data,
            skill_name=self.name,
        )
