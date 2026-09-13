"""
Sprint 3 Live Verification Script
Calls /model/status and /chat with all 3 skill types and prints raw responses.
"""

import json
import httpx

BASE = "http://localhost:8000"

def pretty(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)
    print(json.dumps(data, indent=2))

# 1. Model Status
resp = httpx.get(f"{BASE}/model/status", timeout=10)
pretty("GET /model/status", resp.json())

# 2. Grounded Q&A — factual question
resp = httpx.post(
    f"{BASE}/chat",
    json={"message": "What strategies does Lenny recommend for achieving product-market fit?"},
    timeout=30,
)
pretty("POST /chat — Grounded Q&A (factual question)", resp.json())

# 3. Ship 30 for 30 — essay request
resp = httpx.post(
    f"{BASE}/chat",
    json={"message": "Write a Ship 30 essay about building a growth strategy for an early stage startup"},
    timeout=60,
)
pretty("POST /chat — Ship 30 for 30 (essay request)", resp.json())

# 4. Artifact-Generation — doc/HTML request
resp = httpx.post(
    f"{BASE}/chat",
    json={"message": "Generate an HTML component showing a retention metrics dashboard"},
    timeout=30,
)
pretty("POST /chat — Artifact-Generation (generate HTML request)", resp.json())
