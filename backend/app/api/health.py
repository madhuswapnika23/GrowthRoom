"""
Health-check endpoints.

GET /health       — API liveness
GET /health/db    — PostgreSQL connectivity
GET /health/llm   — LLM provider reachability (placeholder)
"""

from __future__ import annotations

import os
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import engine
from app.models.responses import ErrorDetail, ErrorEnvelope, HealthStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthStatus,
    summary="API liveness check",
)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service="backend")


# ---------------------------------------------------------------------------
# /health/db
# ---------------------------------------------------------------------------

@router.get(
    "/health/db",
    response_model=HealthStatus,
    summary="Database connectivity check",
)
def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return HealthStatus(
            status="ok",
            service="backend",
            checks={"database": "ok"},
        )
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="DB_UNAVAILABLE",
                message="Could not connect to the database.",
            )
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=envelope.model_dump(),
        )


# ---------------------------------------------------------------------------
# /health/llm
# ---------------------------------------------------------------------------

@router.get(
    "/health/llm",
    response_model=HealthStatus,
    summary="LLM provider reachability check",
)
def health_llm():
    """
    Placeholder — checks that a key is configured.
    Will be wired to a real ping once the agent layer is built.
    """
    has_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    if has_openai or has_anthropic:
        provider = "openai" if has_openai else "anthropic"
        return HealthStatus(
            status="ok",
            service="llm",
            checks={"provider": provider, "key_configured": "true"},
        )

    # No keys configured — degrade gracefully
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorEnvelope(
            error=ErrorDetail(
                code="LLM_KEY_MISSING",
                message="No LLM API key is configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.",
            )
        ).model_dump(),
    )
