"""
Agent Router for Growth Room.

Inspects user input messages, applies decision logic to select the appropriate
Agent Skill (grounded_qa, ship30, or artifact_gen), logs the decision with structured
context, and executes the selected skill.
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

# Keyword lists for heuristic routing
SHIP30_KEYWORDS = {
    "ship 30", "ship30", "essay", "post", "atomic essay", "article",
    "thought leadership", "newsletter", "write a post", "write an essay"
}

ARTIFACT_KEYWORDS = {
    "generate doc", "create document", "html snippet", "build ui",
    "create component", "artifact", "generate html", "generate markdown",
    "dashboard component", "ui snippet", "html code"
}


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
        q_lower = query.lower()

        # Check Ship 30 keywords
        for kw in SHIP30_KEYWORDS:
            if kw in q_lower:
                reason = f"Query matched Ship 30 keyword '{kw}'"
                return "ship30", reason

        # Artifact requests commonly combine an action with a format or UI term.
        artifact_action = any(
            phrase in q_lower
            for phrase in ("generate", "create", "build", "make", "design")
        )
        artifact_target = any(
            phrase in q_lower
            for phrase in (
                "artifact", "html", "markdown", "component", "dashboard",
                "ui", "snippet", "document",
            )
        )
        if (artifact_action and artifact_target) or any(
            kw in q_lower for kw in ARTIFACT_KEYWORDS
        ):
            reason = "Query matched Artifact Generation intent"
            return "artifact_gen", reason

        # Default fallback to Grounded Q&A
        reason = "Default fallback for factual/analytical knowledge base query"
        return "grounded_qa", reason

    def route_and_execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        """
        Routes the query, logs structured decision metadata, and executes the chosen skill.
        """
        skill_name, reason = self.route(query)

        logger.info(
            "ROUTER_DECISION | query='%s' | selected_skill='%s' | reason='%s'",
            query, skill_name, reason
        )

        skill = self.skills.get(skill_name, self.skills["grounded_qa"])
        result = skill.execute(query, history, db)
        return result


# Singleton router helper
_router_instance: AgentRouter | None = None


def get_router() -> AgentRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = AgentRouter()
    return _router_instance
