"""
Base interfaces and data structures for Growth Room Agent Skills.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


@dataclass
class SkillResult:
    """Standardized output produced by any agent skill."""
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    grounding_score: float = 0.0
    artifact: Optional[Dict[str, Any]] = None
    skill_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "sources": self.sources,
            "grounding_score": round(self.grounding_score, 4),
            "artifact": self.artifact,
            "skill_name": self.skill_name,
        }


class AgentSkill(ABC):
    """Abstract base class for all agent skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the skill."""

    @abstractmethod
    def execute(self, query: str, history: list[dict], db: Session) -> SkillResult:
        """Execute the skill on user query + conversation history."""
