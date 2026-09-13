"""
Chat API Endpoint for Growth Room.

Accepts session_id + user message, runs the Agent Router → Skill execution,
persists the chat turn, sources, and generated artifacts to Postgres,
and returns a structured response for the frontend.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.router import get_router
from app.db.models import Session as DBSession, Message as DBMessage, Source as DBSource, Artifact as DBArtifact
from app.db.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


# Request payload
class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="UUID of existing conversation session. Created if omitted.")
    message: str = Field(..., min_length=1, description="User question or prompt.")


# Response payloads
class SourceItem(BaseModel):
    episode_title: str
    guest: Optional[str] = None
    segment_timestamp: Optional[str] = None
    relevance_score: Optional[float] = None
    source_url: Optional[str] = None


class ArtifactItem(BaseModel):
    type: str  # "markdown" | "html"
    content: str


class ChatResponseData(BaseModel):
    session_id: str
    message_id: str
    content: str
    skill_used: str
    grounding_score: float
    sources: List[SourceItem] = []
    artifact: Optional[ArtifactItem] = None


class ChatResponseEnvelope(BaseModel):
    status: str = "ok"
    data: ChatResponseData


@router.post("", response_model=ChatResponseEnvelope)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint.
    Processes user message through router → skill, persists to DB, and returns response.
    """
    # 1. Resolve or create Session
    db_session = None
    if payload.session_id:
        try:
            session_uuid = uuid.UUID(payload.session_id)
            db_session = db.query(DBSession).filter(DBSession.id == session_uuid).first()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session_id UUID format."
            )

    if not db_session:
        db_session = DBSession(id=uuid.uuid4())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

    session_id_str = str(db_session.id)

    # 2. Fetch history for session
    history_records = (
        db.query(DBMessage)
        .filter(DBMessage.session_id == db_session.id)
        .order_by(DBMessage.created_at.asc())
        .all()
    )
    history = [{"role": msg.role, "content": msg.content} for msg in history_records]

    # 3. Persist user message
    user_msg = DBMessage(
        id=uuid.uuid4(),
        session_id=db_session.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    db.commit()

    # 4. Route and execute Skill
    router = get_router()
    result = router.route_and_execute(payload.message, history, db)

    # 5. Persist assistant message
    assistant_msg_id = uuid.uuid4()
    assistant_msg = DBMessage(
        id=assistant_msg_id,
        session_id=db_session.id,
        role="assistant",
        content=result.content,
    )
    db.add(assistant_msg)
    db.commit()

    # 6. Persist sources if any
    sources_out: List[SourceItem] = []
    for src in result.sources:
        db_src = DBSource(
            id=uuid.uuid4(),
            message_id=assistant_msg_id,
            episode_title=src.get("episode_title", "Unknown Episode"),
            segment_timestamp=src.get("segment_timestamp"),
            relevance_score=src.get("relevance_score"),
            source_url=src.get("source_url"),
        )
        db.add(db_src)
        sources_out.append(SourceItem(
            episode_title=src.get("episode_title", ""),
            guest=src.get("guest"),
            segment_timestamp=src.get("segment_timestamp"),
            relevance_score=src.get("relevance_score"),
            source_url=src.get("source_url"),
        ))

    # 7. Persist artifact if any
    artifact_out: Optional[ArtifactItem] = None
    if result.artifact:
        art_type = result.artifact.get("type", "markdown").lower()
        if art_type not in ("markdown", "html"):
            art_type = "markdown"
        art_content = str(result.artifact.get("content", ""))

        db_art = DBArtifact(
            id=uuid.uuid4(),
            message_id=assistant_msg_id,
            type=art_type,
            content=art_content,
        )
        db.add(db_art)
        artifact_out = ArtifactItem(type=art_type, content=art_content)

    db.commit()

    # 8. Return response
    return ChatResponseEnvelope(
        status="ok",
        data=ChatResponseData(
            session_id=session_id_str,
            message_id=str(assistant_msg_id),
            content=result.content,
            skill_used=result.skill_name,
            grounding_score=result.grounding_score,
            sources=sources_out,
            artifact=artifact_out,
        )
    )
