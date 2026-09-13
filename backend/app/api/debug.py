"""
Debug API — dev-only endpoint for sanity-checking retrieval quality.

Guarded by ENABLE_DEBUG_ENDPOINTS env var (defaults to "false").
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.retrieval.retriever import retrieve

router = APIRouter(prefix="/debug", tags=["debug"])

_ENABLED = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() in ("true", "1", "yes")


@router.get("/retrieve")
def debug_retrieve(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
    db: Session = Depends(get_db),
):
    """
    Dev-only endpoint: retrieve top-K chunks for a query.
    Returns raw chunks with similarity scores and source metadata.
    """
    if not _ENABLED:
        return {"error": "Debug endpoints are disabled. Set ENABLE_DEBUG_ENDPOINTS=true"}

    results = retrieve(query=q, db=db, top_k=top_k)

    return {
        "query": q,
        "top_k": top_k,
        "result_count": len(results),
        "results": [r.to_dict() for r in results],
    }
