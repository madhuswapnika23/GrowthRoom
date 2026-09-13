"""
Text chunker — splits transcript text into fixed-token-window chunks.

Strategy: Fixed-token window (512 tokens, 64-token overlap)
Why: Lenny's Podcast transcripts are plain text without speaker annotations,
     making speaker-turn chunking infeasible. Fixed-token windows give
     consistent chunk sizes for uniform embedding quality and retrieval scoring.
     Overlap prevents information loss at chunk boundaries.

Token counting uses tiktoken (cl100k_base encoding) for accuracy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)

# Use cl100k_base — the encoding used by GPT-4 / text-embedding models
_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    """A single text chunk with metadata."""
    text: str
    token_count: int
    chunk_index: int


def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[Chunk]:
    """
    Split text into chunks of at most `max_tokens` tokens with `overlap`
    token overlap between consecutive chunks.

    Tries to break at sentence boundaries ('. ') where possible, falling back
    to the hard token limit.

    Args:
        text: The full text to chunk.
        max_tokens: Maximum number of tokens per chunk.
        overlap: Number of overlapping tokens between consecutive chunks.

    Returns:
        List of Chunk objects in order.
    """
    if not text or not text.strip():
        return []

    tokens = _ENCODING.encode(text)
    total_tokens = len(tokens)

    if total_tokens <= max_tokens:
        return [Chunk(text=text.strip(), token_count=total_tokens, chunk_index=0)]

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 0
    step = max_tokens - overlap

    while start < total_tokens:
        end = min(start + max_tokens, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text_raw = _ENCODING.decode(chunk_tokens).strip()

        # Try to find a sentence boundary to break on (only if not the last chunk)
        if end < total_tokens:
            # Look for the last sentence-ending punctuation in the chunk
            for sep in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
                last_sep = chunk_text_raw.rfind(sep)
                if last_sep > len(chunk_text_raw) * 0.5:  # only if past halfway
                    # Re-encode up to that boundary to get actual token count
                    trimmed = chunk_text_raw[: last_sep + len(sep)]
                    trimmed_tokens = _ENCODING.encode(trimmed)
                    chunk_text_raw = trimmed.strip()
                    chunk_tokens = trimmed_tokens
                    break

        if chunk_text_raw:
            chunks.append(
                Chunk(
                    text=chunk_text_raw,
                    token_count=len(chunk_tokens),
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        # Advance by step, but if we trimmed at a sentence boundary,
        # advance by the actual trimmed token count minus overlap
        actual_advance = max(len(chunk_tokens) - overlap, step)
        start += actual_advance

        # Safety: if we're not advancing, force advance
        if actual_advance <= 0:
            start += step

    return chunks
