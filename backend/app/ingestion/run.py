"""
Ingestion runner — orchestrates the full pipeline:
  1. Clone / pull the transcript repo
  2. Load and parse each transcript
  3. Chunk each transcript into fixed-token windows
  4. Generate embeddings for all chunks
  5. Upsert chunks + embeddings into Postgres

Usage:
  python -m app.ingestion.run             # full ingestion
  python -m app.ingestion.run --refresh   # same thing (idempotent)
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from app.db.session import SessionLocal
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import get_embedding_service
from app.ingestion.loader import clone_or_pull, load_transcripts
from app.ingestion.store import ChunkRecord, get_chunk_count, upsert_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def run_ingestion(
    repo_url: str | None = None,
    repo_path: str | None = None,
    max_tokens: int = 512,
    overlap: int = 64,
) -> dict:
    """
    Run the full ingestion pipeline. Returns stats dict.
    """
    repo_url = repo_url or os.getenv(
        "TRANSCRIPT_REPO_URL",
        "https://github.com/ChatPRD/lennys-podcast-transcripts.git",
    )
    repo_path = repo_path or os.getenv("TRANSCRIPT_REPO_PATH", "./transcript_repo")

    start = time.time()

    # 1. Clone / pull
    logger.info("=== Step 1: Clone / pull transcript repo ===")
    clone_or_pull(repo_url, repo_path)

    # 2. Load transcripts
    logger.info("=== Step 2: Loading transcripts ===")
    transcripts = list(load_transcripts(repo_path))
    logger.info("Loaded %d transcripts", len(transcripts))

    # 3. Chunk
    logger.info("=== Step 3: Chunking transcripts ===")
    all_chunk_records: list[ChunkRecord] = []
    all_texts: list[str] = []

    for doc in transcripts:
        chunks = chunk_text(doc.body_text, max_tokens=max_tokens, overlap=overlap)
        for chunk in chunks:
            all_chunk_records.append(
                ChunkRecord(
                    episode_title=doc.episode_title,
                    guest=doc.guest,
                    youtube_url=doc.youtube_url,
                    publish_date=doc.publish_date,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    token_count=chunk.token_count,
                    embedding=[],  # placeholder — filled after embedding
                )
            )
            all_texts.append(chunk.text)

    logger.info("Total chunks: %d", len(all_chunk_records))

    # 4. Embed and store each batch so an interrupted run keeps its progress.
    logger.info("=== Step 4: Generating embeddings ===")
    embedder = get_embedding_service()
    batch_size = 256
    affected = 0
    db = SessionLocal()
    try:
        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i : i + batch_size]
            logger.info("  Embedding batch %d–%d of %d", i, i + len(batch), len(all_texts))
            batch_embeddings = embedder.embed(batch)

            batch_records = all_chunk_records[i : i + len(batch)]
            for rec, emb in zip(batch_records, batch_embeddings):
                rec.embedding = emb

            affected += upsert_chunks(db, batch_records)

        total = get_chunk_count(db)
    finally:
        db.close()

    elapsed = time.time() - start
    stats = {
        "episodes_loaded": len(transcripts),
        "chunks_created": len(all_chunk_records),
        "rows_affected": affected,
        "total_chunks_in_db": total,
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info("=== Ingestion complete ===")
    for k, v in stats.items():
        logger.info("  %s: %s", k, v)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Run knowledge-base ingestion")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-run ingestion (idempotent — won't duplicate rows)",
    )
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=64)
    args = parser.parse_args()

    run_ingestion(max_tokens=args.max_tokens, overlap=args.overlap)


if __name__ == "__main__":
    main()
