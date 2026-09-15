"""
Ship 30 for 30 Skill for Growth Room.

Encodes core Ship 30 for 30 essay principles:
  1. Strong Hook: Grab attention immediately in line 1.
  2. Skimmable Formatting: Short paragraphs, headers (##), bullet points, bold key terms.
  3. Narrative Progression: Hook -> Core Insight -> Key Principles/Steps -> 1 Actionable Takeaway.
  4. Single Actionable Takeaway: Exactly one clear thing the reader can do today.
  5. Strict RAG Grounding: All core claims sourced exclusively from retrieved podcast transcripts.
  6. Target Length: ~800-1,250 words for a complete, well-developed essay.

Output contract:
  - content  : short summary sentence for the chat panel (never the full essay)
  - artifact : { type: "markdown", content: <full essay> }
  - sources  : retrieved transcript chunks used as evidence
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

Your goal is to transform the provided podcast knowledge base insights into a high-impact, skimmable Atomic Essay.

SHIP 30 FOR 30 WRITING RULES (follow all strictly):
1. HOOK: Start with a strong 1-2 line hook -- bold statement, counter-intuitive truth, or provocative question. No filler intros.
2. SKIMMABLE FORMATTING:
   - Use descriptive section headers (## Section Title).
   - Keep paragraphs short: 1-4 sentences maximum.
   - Use bullet points (- item) and **bold text** for key concepts and data points.
3. NARRATIVE PROGRESSION -- structure must follow this exact arc:
   a. Hook (2-3 lines)
   b. The Core Problem or Insight (1-2 short paragraphs)
   c. 3-4 Key Lessons or Principles -- each grounded in a specific transcript excerpt with the episode/guest name
   d. One Specific Actionable Takeaway (labeled: ### One Action to Take Today)
4. SINGLE ACTIONABLE TAKEAWAY: End with exactly ONE concrete action the reader can execute immediately. Be specific.
5. STRICT GROUNDING: Every factual claim, quote, or data point MUST come from the provided transcript context. Do NOT invent facts or use outside knowledge.
6. TARGET LENGTH: Write ~800-1,250 words. A short, punchy essay is acceptable; a single paragraph is not.

Return ONLY the essay content (no wrapping JSON, no code fences)."""


class Ship30Skill(AgentSkill):
    """Skill for generating Ship 30 for 30 style structured essays grounded in RAG."""

    @property
    def name(self) -> str:
        return "ship30"

    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        logger.info("Executing Ship30Skill for query: '%s'", query)

        # 1. Retrieve relevant podcast transcript chunks (top_k=6 for richer essay material)
        retrieved_chunks: List[RetrievedChunk] = retrieve(query, db, top_k=6, min_score=0.20)

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

        prompt = f"""KNOWLEDGE BASE CONTEXT ({len(retrieved_chunks)} transcript excerpts):
{context_str}

USER REQUEST:
{query}

Write a complete Ship 30 for 30 essay following all rules in the system prompt.
Ground every key claim in one of the {len(retrieved_chunks)} provided sources above.
Return ONLY the essay text -- no JSON, no code fences."""

        # 3. Generate essay
        llm = get_llm_service()
        essay_content, provider_used = llm.generate(prompt, system=SHIP30_SYSTEM_PROMPT, temperature=0.3)

        logger.info(
            "Ship30Skill generated essay: provider=%s, word_count~%d, sources=%d",
            provider_used, len(essay_content.split()), len(sources_list),
        )

        # 4. Build artifact -- full essay goes here; a brief summary goes to the chat panel
        artifact_data = {
            "type": "markdown",
            "content": essay_content,
        }

        # Chat panel gets a short confirmation so the conversation stays readable
        episode_names = ", ".join(
            dict.fromkeys(s["episode_title"] for s in sources_list if s["episode_title"])
        )
        chat_summary = (
            f"**Ship 30 essay generated** -- grounded in {len(sources_list)} transcript sources "
            f"({episode_names[:120]}{'...' if len(episode_names) > 120 else ''}). "
            f"The full essay is in the **Artifact panel** on the right."
        )

        return SkillResult(
            content=chat_summary,
            sources=sources_list,
            grounding_score=float(avg_score),
            artifact=artifact_data,
            skill_name=self.name,
        )
