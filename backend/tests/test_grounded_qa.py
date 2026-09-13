"""
Tests for Grounded Q&A Skill out-of-scope question handling.
"""

from unittest.mock import MagicMock
from app.agent.skills.grounded_qa import GroundedQASkill


def test_grounded_qa_out_of_scope_returns_not_enough_material():
    """Verify that an out-of-scope question returns the explicit 'not enough material' response."""
    skill = GroundedQASkill()

    # Mock DB session
    mock_db = MagicMock()

    # Out of scope question that returns no matches / low similarity
    out_of_scope_query = "What is the airspeed velocity of an unladen swallow?"

    result = skill.execute(out_of_scope_query, history=[], db=mock_db)

    assert "don't have enough source material" in result.content.lower()
    assert result.sources == []
    assert result.grounding_score == 0.0
    assert result.artifact is None
    assert result.skill_name == "grounded_qa"
