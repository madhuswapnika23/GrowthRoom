"""
Agent Router for Growth Room.

Inspects user input messages, applies decision logic to select the appropriate
Agent Skill (grounded_qa, ship30, or artifact_gen), logs the decision with structured
context, and executes the selected skill.

Routing priority (highest → lowest):
  1. Ship30 — essay/post writing requests
  2. ArtifactGen — page/doc/HTML generation requests
  3. GroundedQA — default factual Q&A
"""

from __future__ import annotations

import logging
from typing import Dict
from sqlalchemy.orm import Session

from app.agent.skills.base import AgentSkill, SkillResult
from app.agent.skills.grounded_qa import GroundedQASkill
from app.agent.skills.ship30 import Ship30Skill
from app.agent.skills.artifact_gen import ArtifactGenSkill

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ship 30 for 30 — phrase/keyword triggers
# ---------------------------------------------------------------------------
# These are checked first. Any substring match → ship30 skill.
SHIP30_TRIGGERS = [
    "ship 30", "ship30", "atomic essay",
    "write a post", "write me a post", "draft a post", "draft an essay",
    "write an essay", "write me an essay",
    "write an article", "write me an article",
    "create a post", "create an essay", "create an article",
    "turn this into an essay", "turn this into a post",
    "thought leadership", "newsletter",
    # standalone "post" and "essay" as whole words are intentionally NOT here
    # because they're too broad; use the multi-word phrases above instead.
]

# ---------------------------------------------------------------------------
# Artifact-generation — explicit page/doc/HTML triggers
# ---------------------------------------------------------------------------
ARTIFACT_EXPLICIT_PHRASES = [
    "one-pager", "onepager", "one pager",
    "landing page", "landing-page",
    "make me a page", "make me a doc", "make me a dashboard",
    "make a one-pager", "make a landing page",
    "generate a doc", "generate a page", "generate a dashboard",
    "create a doc", "create a page", "create a one-pager",
    "build a page", "build a dashboard", "build a one-pager",
    "turn this into a page", "turn this into a dashboard",
    "turn this into html", "turn this into a doc",
    # legacy keyword set kept for backward compat
    "generate doc", "create document", "html snippet", "build ui",
    "create component", "artifact", "generate html", "generate markdown",
    "dashboard component", "ui snippet", "html code",
]

# Artifact fallback: action verb + target noun combo
ARTIFACT_ACTION_VERBS = ("generate", "create", "build", "make", "design")
ARTIFACT_TARGET_NOUNS = (
    "artifact", "html", "markdown", "component", "dashboard",
    "ui", "snippet", "document",
)


class AgentRouter:
    """Router for selecting and executing agent skills based on user intent."""

    def __init__(self):
        self.skills: Dict[str, AgentSkill] = {
            "grounded_qa": GroundedQASkill(),
            "ship30": Ship30Skill(),
            "artifact_gen": ArtifactGenSkill(),
        }

    def route(self, query: str) -> tuple[str, str]:
        """
        Determines the target skill and reason based on input query.

        Returns: (skill_name, reasoning_summary)
        """
        q = query.lower()

        # 1. Ship30 — checked first (highest priority)
        for trigger in SHIP30_TRIGGERS:
            if trigger in q:
                reason = f"Ship30 trigger matched: '{trigger}'"
                return "ship30", reason

        # 2. Artifact generation — explicit phrases
        for phrase in ARTIFACT_EXPLICIT_PHRASES:
            if phrase in q:
                reason = f"ArtifactGen explicit phrase matched: '{phrase}'"
                return "artifact_gen", reason

        # 3. Artifact generation — action + target combo
        has_action = any(v in q for v in ARTIFACT_ACTION_VERBS)
        has_target = any(n in q for n in ARTIFACT_TARGET_NOUNS)
        if has_action and has_target:
            reason = "ArtifactGen action+target combo matched"
            return "artifact_gen", reason

        # 4. Default → Grounded Q&A
        reason = "Default: factual/analytical knowledge-base query"
        return "grounded_qa", reason

    def route_and_execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        """
        Routes the query, logs structured decision metadata, and executes the chosen skill.
        """
        skill_name, reason = self.route(query)

        logger.info(
            "ROUTER_DECISION | skill=%r | reason=%r | query=%r",
            skill_name, reason, query[:120],
        )

        skill = self.skills.get(skill_name, self.skills["grounded_qa"])
        result = skill.execute(query, history, db)

        logger.info(
            "SKILL_RESULT | skill=%r | grounding=%.3f | has_artifact=%s | sources=%d",
            result.skill_name,
            result.grounding_score,
            result.artifact is not None,
            len(result.sources),
        )

        return result


# Singleton router helper
_router_instance: AgentRouter | None = None


def get_router() -> AgentRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = AgentRouter()
    return _router_instance
