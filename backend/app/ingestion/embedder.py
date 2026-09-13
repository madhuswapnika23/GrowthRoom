"""
Embedding service — wraps fastembed (ONNX-runtime) for batch text embedding.

Model: BAAI/bge-small-en-v1.5  (default fastembed model)
Why:
  - ONNX-based: zero PyTorch/CUDA dependency → small Docker image
  - 384-dim output: same dimension as the previous all-MiniLM-L6-v2 model,
    so the db schema and IVFFlat index are unchanged
  - ~67 MB model download (cached after first run)
  - Comparable semantic-search quality to MiniLM on standard benchmarks
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingService:
    """Singleton-ish embedding service that loads the ONNX model once."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", _DEFAULT_MODEL)
        logger.info("Loading fastembed model: %s", self.model_name)
        self._model = TextEmbedding(model_name=self.model_name)
        # fastembed exposes dim via the model's embedding size; probe it once
        self._dim: int | None = None
        logger.info("fastembed model ready: %s", self.model_name)

    @property
    def dimension(self) -> int:
        if self._dim is None:
            # Probe dimension by embedding a dummy sentence
            dummy = list(self._model.embed(["probe"]))
            self._dim = len(dummy[0])
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Returns list of float vectors (L2-normalised by fastembed by default).
        """
        if not texts:
            return []
        # fastembed.embed() returns a generator of numpy arrays
        embeddings = list(self._model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]


@lru_cache(maxsize=1)
def get_embedding_service(model_name: str | None = None) -> EmbeddingService:
    """Get or create the singleton EmbeddingService."""
    return EmbeddingService(model_name)
