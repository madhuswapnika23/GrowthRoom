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

import json
import logging
import os
import re
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
        if system and "Artifact Generator" in system:
            return (
                '{"type":"html","content":"'
                '<section style=\\"font-family:system-ui,sans-serif;padding:24px;'
                'color:#1f2937;background:#ffffff;max-width:720px;\\">'
                '<h2 style=\\"margin:0 0 20px;\\">Retention metrics</h2>'
                '<div style=\\"display:grid;grid-template-columns:repeat(3,1fr);'
                'gap:12px;\\">'
                '<div style=\\"padding:16px;background:#f3f4f6;border-radius:8px;\\">'
                '<small>Activation</small><strong style=\\"display:block;font-size:24px;\\">68%</strong></div>'
                '<div style=\\"padding:16px;background:#f3f4f6;border-radius:8px;\\">'
                '<small>Day 30 retention</small><strong style=\\"display:block;font-size:24px;\\">42%</strong></div>'
                '<div style=\\"padding:16px;background:#f3f4f6;border-radius:8px;\\">'
                '<small>Weekly active users</small><strong style=\\"display:block;font-size:24px;\\">18.4k</strong></div>'
                '</div></section>"}'
            )
        # Extract context if present in prompt
        if "No relevant context found" in prompt or "NOT ENOUGH MATERIAL" in prompt:
            return "I don't have enough source material in the knowledge base to answer this question accurately."
        
        # Simple extraction synthesis for testing/offline environments
        return (
            "Based on the provided podcast context, key insights include focus on core metrics, "
            "rigorous customer interviews, and iterative product validation. "
            "(Generated via fallback provider)"
        )


class FallbackMockProvider(LLMProvider):
    """
    Fallback Provider used when neither Cloud (Anthropic) nor Local (Ollama) is operational.
    Generates dynamic, context-aware responses, Ship 30 essays, and HTML artifacts.
    """

    @property
    def name(self) -> str:
        return "fallback_mock"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        logger.warning("Using FallbackMockProvider to generate answer")
        system_str = (system or "").lower()
        prompt_lower = prompt.lower()

        # Check for insufficient material signal
        if "no relevant context found" in prompt_lower or "not enough material" in prompt_lower:
            return "I don't have enough source material in the knowledge base to answer this question accurately."

        # Parse retrieved sources / context chunks from prompt
        source_matches = re.findall(r"\[Source \d+ - Episode: ([^\]]+)\]\s*(.*?)(?=\[Source \d+|\Z)", prompt, re.DOTALL)
        if not source_matches:
            source_matches = re.findall(r"--- Chunk \d+ \(([^\)]+)\) ---\s*(.*?)(?=--- Chunk \d+|\Z)", prompt, re.DOTALL)

        extracted_insights = []
        episode_names = set()
        for ep, text in source_matches:
            ep_clean = ep.strip()
            episode_names.add(ep_clean)
            sentences = [s.strip() for s in text.strip().split(".") if len(s.strip()) > 20]
            if sentences:
                extracted_insights.append((ep_clean, sentences[0]))

        ep_summary = ", ".join(list(episode_names)[:3]) if episode_names else "Lenny's Podcast transcripts"

        # 1. Handle HTML Artifact Generation
        if "artifact generator" in system_str or "json" in system_str or "html" in prompt_lower:
            topic = "Growth & Retention Metrics"
            if "retention" in prompt_lower:
                topic = "Retention Loop Framework"
            elif "market fit" in prompt_lower or "pmf" in prompt_lower:
                topic = "Product-Market Fit Scorecard"

            return json.dumps({
                "type": "html",
                "content": (
                    f'<div style="font-family: system-ui, -apple-system, sans-serif; padding: 24px; background: #0d1117; color: #c9d1d9; border-radius: 12px; border: 1px solid #30363d;">'
                    f'<h2 style="color: #58a6ff; margin-top: 0; font-size: 20px; font-weight: 600;">{topic}</h2>'
                    f'<p style="color: #8b949e; font-size: 13px; margin-bottom: 20px;">Grounded in insights from {ep_summary}</p>'
                    f'<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px;">'
                    f'<div style="background: #161b22; padding: 16px; border-radius: 8px; border: 1px solid #30363d;">'
                    f'<div style="font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em;">Activation Rate</div>'
                    f'<div style="font-size: 26px; font-weight: 700; color: #39d353; margin-top: 4px;">64.2%</div>'
                    f'<div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Target: &gt;60%</div>'
                    f'</div>'
                    f'<div style="background: #161b22; padding: 16px; border-radius: 8px; border: 1px solid #30363d;">'
                    f'<div style="font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em;">Day-30 Retention</div>'
                    f'<div style="font-size: 26px; font-weight: 700; color: #58a6ff; margin-top: 4px;">41.8%</div>'
                    f'<div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Good SaaS benchmark</div>'
                    f'</div>'
                    f'<div style="background: #161b22; padding: 16px; border-radius: 8px; border: 1px solid #30363d;">'
                    f'<div style="font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em;">Payback Period</div>'
                    f'<div style="font-size: 26px; font-weight: 700; color: #d2a8ff; margin-top: 4px;">8.5 mos</div>'
                    f'<div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Efficient capital use</div>'
                    f'</div>'
                    f'</div>'
                    f'<div style="margin-top: 20px; padding: 16px; background: #161b22; border-radius: 8px; border-left: 4px solid #58a6ff;">'
                    f'<strong style="color: #f0f6fc; font-size: 13px;">Key Action Item:</strong>'
                    f'<p style="margin: 6px 0 0; font-size: 13px; color: #8b949e; line-height: 1.5;">'
                    f'Focus on building compounding viral or retention loops into your core product workflow before scaling paid acquisition.'
                    f'</p></div></div>'
                )
            })

        # 2. Handle Ship 30 for 30 Essay Generation
        if "ship 30" in system_str or "ship30" in system_str or "essay" in prompt_lower:
            bullets_html = ""
            if extracted_insights:
                for ep, insight in extracted_insights[:3]:
                    bullets_html += f"- **{ep}**: {insight}.\n"
            else:
                bullets_html = (
                    "- **Focus on Activation First**: Solve early onboarding friction before attempting paid growth.\n"
                    "- **Identify Your Core Habit Loop**: Determine the key action users complete that predicts 30-day retention.\n"
                    "- **Track Counter-Metrics**: Ensure aggressive retention optimization doesn't degrade user satisfaction.\n"
                )

            return (
                f"# 🚀 The Core Principles of Product & Growth Leadership\n\n"
                f"**Most startups fail not because they can't acquire users, but because they can't retain them.**\n\n"
                f"If your product's bucket is leaky, every marketing dollar spent is wasted. "
                f"Synthesizing insights from **{ep_summary}**, here is how top-tier product leaders build scalable, defensible growth engines.\n\n"
                f"## 1. Solve Retention Before Scaling Acquisition\n\n"
                f"Before launching aggressive marketing campaigns, establish a flat retention curve. "
                f"Sustainable growth is driven by compounding loops, not one-off acquisition spikes.\n\n"
                f"## 2. Key Insights Grounded in Lenny's Podcast\n\n"
                f"{bullets_html}\n"
                f"## 3. Build Compounding Growth Flywheels\n\n"
                f"Identify the natural loop where user engagement creates outputs that attract new users—whether through content, referrals, or network effects.\n\n"
                f"---\n\n"
                f"### 💡 **One Actionable Takeaway Today**\n\n"
                f"Audit your product onboarding flow today and eliminate at least 2 friction steps between user sign-up and your core 'Habit Moment'."
            )

        # 3. Handle Grounded Q&A
        if extracted_insights:
            synthesis_points = "\n".join([f"• **{ep}**: {insight}." for ep, insight in extracted_insights[:4]])
            return (
                f"Based on the transcript context from **{ep_summary}**, here are the key insights:\n\n"
                f"{synthesis_points}\n\n"
                f"In summary, successful growth requires focusing on core activation metrics, conducting continuous customer interviews, and validating value retention before expanding acquisition channels."
            )

        return (
            f"Based on the transcript knowledge base ({ep_summary}), key takeaways include focusing on core user retention, "
            f"setting clear product metrics, and establishing repeatable feedback loops with customers."
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
        self.preferred_provider: str = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()

    def _get_preferred_provider_name(self) -> str:
        return getattr(self, "preferred_provider", os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower())

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
        pref = self._get_preferred_provider_name()
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
