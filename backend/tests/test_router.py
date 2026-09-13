"""
Unit tests for Agent Router decision logic.
"""

from app.agent.router import get_router


def test_router_grounded_qa_factual_query():
    router = get_router()
    query = "What are the top metrics for product-market fit according to Lenny?"
    skill_name, reason = router.route(query)
    assert skill_name == "grounded_qa"
    assert "default fallback" in reason.lower() or "factual" in reason.lower()


def test_router_ship30_essay_request():
    router = get_router()
    query = "Write a Ship 30 essay on customer retention strategies"
    skill_name, reason = router.route(query)
    assert skill_name == "ship30"
    assert "ship 30" in reason.lower() or "essay" in reason.lower()


def test_router_artifact_gen_doc_request():
    router = get_router()
    query = "Generate HTML component for retention metrics dashboard"
    skill_name, reason = router.route(query)
    assert skill_name == "artifact_gen"
    assert "artifact" in reason.lower() or "html" in reason.lower()
