"""
Tests for session persistence and API contract validation.
Validates GET /sessions, GET /sessions/{id}, POST /chat, and DELETE /sessions.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.main import app
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_api_contract_and_persistence():
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg2://growthroom:changeme_dev@localhost:5432/growthroom")
    engine = create_engine(url)
    db = sessionmaker(bind=engine)()
    client = TestClient(app)

    # 1. Create a session via POST /chat
    resp = client.post("/chat", json={"message": "What is the retention loop?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "data" in data
    
    session_id = data["data"]["session_id"]
    msg_id = data["data"]["message_id"]
    
    # 2. Add second message to same session
    resp2 = client.post("/chat", json={"session_id": session_id, "message": "Give me more details."})
    assert resp2.status_code == 200
    assert resp2.json()["data"]["session_id"] == session_id
    
    # 3. GET /sessions (API List Contract)
    list_resp = client.get("/sessions")
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert len(list_data) >= 1
    
    # Find our session
    my_sess = next((s for s in list_data if s["session_id"] == session_id), None)
    assert my_sess is not None
    assert my_sess["title"].startswith("What is the retention loop?")
    assert my_sess["message_count"] == 4  # 2 user msgs + 2 assistant msgs
    assert "created_at" in my_sess
    
    # 4. GET /sessions/{id} (API Detail Contract & Persistence)
    detail_resp = client.get(f"/sessions/{session_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    
    messages = detail_data["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is the retention loop?"
    assert messages[1]["role"] == "assistant"
    
    # 5. Delete session
    del_resp = client.delete(f"/sessions/{session_id}")
    assert del_resp.status_code == 200
    
    # 6. Verify Deletion
    get_again = client.get(f"/sessions/{session_id}")
    assert get_again.status_code == 404
