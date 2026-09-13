"""
Sessions API — list and fetch conversation sessions with metadata.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.db.models import (
    Session as DBSession,
    Message as DBMessage,
    Source as DBSource,
    Artifact as DBArtifact,
)
from app.db.session import get_db

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCard(BaseModel):
    session_id: str
    title: str          # first user message, truncated
    created_at: str
    message_count: int
    artifact_count: int
    latest_grounding_score: Optional[float]


class SessionsListResponse(BaseModel):
    status: str = "ok"
    data: List[SessionCard]


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    grounding_score: Optional[float] = None
    sources: List[Dict[str, Any]] = []
    artifact: Optional[Dict[str, Any]] = None


class SessionDetailResponse(BaseModel):
    status: str = "ok"
    data: Dict[str, Any]


@router.get("", response_model=SessionsListResponse)
def list_sessions(db: Session = Depends(get_db)):
    """
    Return all sessions ordered by newest first, with metadata:
    - title: first user message (truncated to 60 chars)
    - created_at: ISO timestamp
    - message_count
    - artifact_count
    - latest_grounding_score: from the most recent assistant message's sources
    """
    sessions = (
        db.query(DBSession)
        .order_by(DBSession.created_at.desc())
        .all()
    )

    cards: List[SessionCard] = []
    for sess in sessions:
        messages = sorted(sess.messages, key=lambda m: m.created_at)
        first_user_msg = next((m for m in messages if m.role == "user"), None)
        title = (first_user_msg.content[:60] + "…") if first_user_msg and len(first_user_msg.content) > 60 else (first_user_msg.content if first_user_msg else "New session")

        artifact_count = sum(len(m.artifacts) for m in messages)

        # Latest grounding score from sources of most recent assistant message
        latest_grounding: Optional[float] = None
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.sources:
                scores = [s.relevance_score for s in msg.sources if s.relevance_score is not None]
                if scores:
                    latest_grounding = round(sum(scores) / len(scores), 3)
                    break

        cards.append(SessionCard(
            session_id=str(sess.id),
            title=title,
            created_at=sess.created_at.isoformat(),
            message_count=len(messages),
            artifact_count=artifact_count,
            latest_grounding_score=latest_grounding,
        ))

    return SessionsListResponse(status="ok", data=cards)


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """
    Return full conversation history for a session including sources and artifacts per message.
    """
    try:
        sess_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    sess = db.query(DBSession).filter(DBSession.id == sess_uuid).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = sorted(sess.messages, key=lambda m: m.created_at)
    msgs_out = []
    for msg in messages:
        sources_out = [
            {
                "episode_title": s.episode_title,
                "segment_timestamp": s.segment_timestamp,
                "relevance_score": s.relevance_score,
                "source_url": s.source_url,
            }
            for s in msg.sources
        ]
        artifact_out = None
        if msg.artifacts:
            art = msg.artifacts[0]
            artifact_out = {"type": art.type, "content": art.content}

        msgs_out.append({
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "sources": sources_out,
            "artifact": artifact_out,
        })

    return SessionDetailResponse(status="ok", data={
        "session_id": session_id,
        "created_at": sess.created_at.isoformat(),
        "messages": msgs_out,
    })


@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session and all its messages, sources, and artifacts."""
    try:
        sess_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    sess = db.query(DBSession).filter(DBSession.id == sess_uuid).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    db.delete(sess)
    db.commit()
    return {"status": "ok", "message": "Session deleted."}
