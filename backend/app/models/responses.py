"""
Pydantic models for all API responses.

Consistent envelope shapes:
  Success  → { "status": "ok", ... }
  Error    → { "error": { "code": str, "message": str, "detail": any } }
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Health responses
# ---------------------------------------------------------------------------

class HealthStatus(BaseModel):
    status: str = Field(..., examples=["ok", "degraded", "error"])
    service: str
    version: str = "0.1.0"
    checks: Optional[Dict[str, str]] = None


class DBHealthStatus(HealthStatus):
    service: str = "database"


class LLMHealthStatus(HealthStatus):
    service: str = "llm"
    provider: Optional[str] = None
