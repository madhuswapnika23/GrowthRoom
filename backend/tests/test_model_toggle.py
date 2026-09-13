"""
Tests for LLM Service provider status and fallback mechanism.
"""

import os
from unittest.mock import patch
from app.agent.llm import get_llm_service, AnthropicProvider, OllamaProvider


def test_model_status_structure():
    """Verify get_status returns expected structure with configured and active provider info."""
    service = get_llm_service()
    status = service.get_status()

    assert "configured_provider" in status
    assert "active_provider" in status
    assert "fallback_active" in status
    assert "providers" in status
    assert "anthropic" in status["providers"]
    assert "ollama" in status["providers"]


def test_model_fallback_triggers_when_primary_fails():
    """Verify that when primary provider fails, fallback triggers cleanly."""
    service = get_llm_service()

    # Mock primary provider is_available to return True but generate to raise Exception
    with patch.object(AnthropicProvider, "is_available", return_value=True), \
         patch.object(AnthropicProvider, "generate", side_effect=RuntimeError("API quota exceeded")), \
         patch.object(OllamaProvider, "is_available", return_value=False):

        response_text, provider_used = service.generate("Test query", system=None)
        assert provider_used == "fallback_mock"
        assert len(response_text) > 0
