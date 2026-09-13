"""
Model status endpoint.
Returns the current active LLM provider, fallback status, and configuration details.
Also exposes a /model/select endpoint for live provider override from the frontend.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.agent.llm import get_llm_service

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/status")
def get_model_status():
    """Get active LLM provider and fallback status."""
    service = get_llm_service()
    status_data = service.get_status()
    return {
        "status": "ok",
        "data": status_data,
    }


class ProviderSelectRequest(BaseModel):
    provider: str  # "anthropic" | "ollama" | "auto"


@router.post("/select")
def select_provider(payload: ProviderSelectRequest):
    """
    Override the active LLM provider at runtime.
    - 'anthropic' — force cloud Claude (falls back if unavailable)
    - 'ollama'    — force local Ollama (falls back if unavailable)
    - 'auto'      — reset to env-configured default with fallback
    """
    valid = {"anthropic", "ollama", "auto"}
    if payload.provider not in valid:
        return {"status": "error", "message": f"Invalid provider. Choose one of {valid}"}

    service = get_llm_service()
    # Update the preferred provider on the singleton
    if payload.provider == "auto":
        import os
        service.preferred_provider = os.getenv("LLM_PROVIDER", "anthropic")
    else:
        service.preferred_provider = payload.provider

    # Return updated status
    return {
        "status": "ok",
        "message": f"Provider preference updated to '{payload.provider}'",
        "data": service.get_status(),
    }
