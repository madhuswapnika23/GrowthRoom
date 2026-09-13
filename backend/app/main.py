"""
Growth Room — FastAPI application factory.

Features:
  - CORS configured for local dev (Vite on :5173)
  - Global exception handler → always returns the error envelope, never raw tracebacks
  - Health router mounted at root
"""

from __future__ import annotations

import logging
import os
import traceback

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health
from app.models.responses import ErrorDetail, ErrorEnvelope

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Growth Room API",
    description="Internal AI assistant powered by Lenny's Podcast transcripts.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # CRA / alternative
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global error handler — never expose raw tracebacks to the client
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorEnvelope(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please try again later.",
            )
        ).model_dump(),
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.api import chat, health, model_status, sessions

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(model_status.router)
app.include_router(sessions.router)

# Debug endpoints — only in dev
if os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() in ("true", "1", "yes"):
    from app.api import debug
    app.include_router(debug.router)

# ---------------------------------------------------------------------------
# Startup log
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    logger.info("🌱 Growth Room API starting up — docs at /docs")
