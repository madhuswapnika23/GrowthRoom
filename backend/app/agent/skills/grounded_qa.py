"""
Grounded Q&A Skill for Growth Room.

Strictly answers user questions grounded in retrieved transcript chunks.
If retrieval is empty or max similarity score is low, returns an explicit
"not enough material" message rather than hallucinating.
Calculates and returns a numeric grounding score alongside cited sources.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.agent.llm import get_llm_service
from app.agent.skills.base import AgentSkill, SkillResult
from app.retrieval.retriever import retrieve, RetrievedChunk

logger = logging.getLogger(__name__)

# Minimum threshold for considering a search match relevant
CONFIDENCE_THRESHOLD = 0.35

SYSTEM_PROMPT = """You are Growth Room's AI assistant powered strictly by Lenny's Podcast transcripts.

CRITICAL INSTRUCTIONS:
1. Answer the user's question using ONLY the provided transcript context.
2. Do NOT use outside knowledge or make assumptions.
3. If the context does not contain enough detail to fully answer the question, state clearly that the knowledge base has limited information on that specific aspect.
4. Keep your answer clear, well-structured, and directly helpful.
5. Reference specific guests or episode topics when present in the context."""


class GroundedQASkill(AgentSkill):
    """Skill for answering factual/analytical questions grounded in podcast knowledge base."""

    @property
    def name(self) -> str:
        return "grounded_qa"

    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        logger.info("Executing GroundedQASkill for query: '%s'", query)

        # 1. Retrieve chunks
        retrieved_chunks: List[RetrievedChunk] = retrieve(query, db, top_k=5, min_score=0.20)

        # Calculate max and avg score
        if not retrieved_chunks:
            max_score = 0.0
            avg_score = 0.0
        else:
            scores = [c.similarity_score for c in retrieved_chunks]
            max_score = max(scores)
            avg_score = sum(scores) / len(scores)

        # 2. Check if retrieval is empty or low confidence
        if not retrieved_chunks or max_score < CONFIDENCE_THRESHOLD:
            logger.info(
                "Low confidence or empty retrieval for query '%s' (max_score=%.4f < threshold=%.2f)",
                query, max_score, CONFIDENCE_THRESHOLD
            )
            return SkillResult(
                content="I don't have enough source material in the knowledge base to answer this question accurately.",
                sources=[],
                grounding_score=0.0,
                artifact=None,
                skill_name=self.name,
            )

        # 3. Format context for prompt
        context_blocks = []
        sources_list: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(retrieved_chunks, start=1):
            guest_str = f" (Guest: {chunk.guest})" if chunk.guest else ""
            header = f"[Source {idx} - Episode: {chunk.episode_title}{guest_str}]"
            context_blocks.append(f"{header}\n{chunk.chunk_text}")

            # Collect source metadata
            sources_list.append({
                "episode_title": chunk.episode_title,
                "guest": chunk.guest,
                "segment_timestamp": f"Chunk {chunk.chunk_index}",
                "relevance_score": round(chunk.similarity_score, 4),
                "source_url": chunk.youtube_url,
            })

        context_str = "\n\n---\n\n".join(context_blocks)

        prompt = f"""RETRIEVED TRANSCRIPT CONTEXT:
{context_str}

USER QUESTION:
{query}

Provide a helpful, grounded answer based strictly on the transcript context above."""

        # 4. Generate completion
        llm = get_llm_service()
        response_text, provider_used = llm.generate(prompt, system=SYSTEM_PROMPT, temperature=0.2)

        # Compute grounding score (0.0 - 1.0)
        grounding_score = float(avg_score)

        return SkillResult(
            content=response_text,
            sources=sources_list,
            grounding_score=grounding_score,
            artifact=None,
            skill_name=self.name,
        )
