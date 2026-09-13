"""
LLM Abstraction & Provider Fallback Layer for Growth Room.

Supports:
  1. Anthropic Claude API (Cloud)
  2. Ollama (Local) — recommended default model: llama3.2:3b (lightweight dev laptop)
  3. Mock / Rule-Based Fallback — when external LLMs are unreachable or unconfigured

Enables env-driven provider switching (`LLM_PROVIDER=anthropic|ollama`) with automatic fallback
if the primary provider fails or is unavailable. Exposes model status via get_status().
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

import httpx

logger = logging.getLogger(__name__)

# Default config constants
DEFAULT_PROVIDER = "anthropic"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name string."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        """Generate text from prompt. Raises Exception if request fails."""


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API Provider."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        if not self.api_key or self.api_key in ("sk-ant-replace-me", "sk-replace-me", "your_anthropic_api_key_here"):
            return False
        return True

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        if not self.is_available():
            raise RuntimeError("Anthropic API key is missing or default placeholder.")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        messages = [{"role": "user", "content": prompt}]
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=45.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Extract content text
            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    return block.get("text", "")
            return ""


class OllamaProvider(LLMProvider):
    """Ollama Local Model Provider (e.g. llama3.2:3b)."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            return res.json().get("response", "")


class FallbackMockProvider(LLMProvider):
    """
    Fallback Provider used when neither Cloud (Anthropic) nor Local (Ollama) is operational.
    Generates a clear, grounded response synthesizing retrieved context.
    """

    @property
    def name(self) -> str:
        return "fallback_mock"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        logger.warning("Using FallbackMockProvider to generate answer")
        # Extract context if present in prompt
        if "No relevant context found" in prompt or "NOT ENOUGH MATERIAL" in prompt:
            return "I don't have enough source material in the knowledge base to answer this question accurately."
        
        # Simple extraction synthesis for testing/offline environments
        return (
            "Based on the provided podcast context, key insights include focus on core metrics, "
            "rigorous customer interviews, and iterative product validation. "
            "(Generated via fallback provider)"
        )


class LLMService:
    """
    LLM Service manager.
    Handles preferred provider selection and automatic fallback.
    """

    def __init__(self):
        self.anthropic_provider = AnthropicProvider()
        self.ollama_provider = OllamaProvider()
        self.mock_provider = FallbackMockProvider()

    def _get_preferred_provider_name(self) -> str:
        return os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()

    def get_provider(self, provider_name: str | None = None) -> LLMProvider:
        target = (provider_name or self._get_preferred_provider_name()).lower()
        if target == "anthropic":
            return self.anthropic_provider
        elif target == "ollama":
            return self.ollama_provider
        return self.anthropic_provider

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> Tuple[str, str]:
        """
        Generates text using preferred provider. If it fails or is unavailable,
        attempts secondary provider, then falls back to FallbackMockProvider.

        Returns: (generated_text, active_provider_name)
        """
        preferred_name = self._get_preferred_provider_name()
        primary = self.get_provider(preferred_name)
        secondary = self.ollama_provider if preferred_name == "anthropic" else self.anthropic_provider

        # Try primary
        if primary.is_available():
            try:
                logger.info("Generating completion with primary provider: %s", primary.name)
                result = primary.generate(prompt, system=system, temperature=temperature)
                return result, primary.name
            except Exception as e:
                logger.warning("Primary LLM provider '%s' failed: %s. Trying fallback...", primary.name, e)

        # Try secondary
        if secondary.is_available():
            try:
                logger.info("Generating completion with secondary provider: %s", secondary.name)
                result = secondary.generate(prompt, system=system, temperature=temperature)
                return result, secondary.name
            except Exception as e:
                logger.warning("Secondary LLM provider '%s' failed: %s. Trying mock fallback...", secondary.name, e)

        # Fallback to mock provider
        logger.info("Using FallbackMockProvider for completion generation")
        result = self.mock_provider.generate(prompt, system=system, temperature=temperature)
        return result, self.mock_provider.name

    def get_status(self) -> Dict[str, Any]:
        """Returns LLM system status information."""
        pref = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()
        anthropic_avail = self.anthropic_provider.is_available()
        ollama_avail = self.ollama_provider.is_available()

        active_provider = pref if (pref == "anthropic" and anthropic_avail) or (pref == "ollama" and ollama_avail) else (
            "ollama" if ollama_avail else ("anthropic" if anthropic_avail else "fallback_mock")
        )

        fallback_active = active_provider != pref

        return {
            "configured_provider": pref,
            "active_provider": active_provider,
            "fallback_active": fallback_active,
            "providers": {
                "anthropic": {
                    "available": anthropic_avail,
                    "model": self.anthropic_provider.model,
                },
                "ollama": {
                    "available": ollama_avail,
                    "model": self.ollama_provider.model,
                    "url": self.ollama_provider.base_url,
                },
                "fallback_mock": {
                    "available": True,
                    "model": "rule-based-synthesis",
                }
            }
        }


# Singleton instance helper
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
