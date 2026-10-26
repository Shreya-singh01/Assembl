"""Sentence-embedding encoders behind a small injectable interface.

* :class:`SentenceTransformerEncoder` - the pretrained Sentence-BERT model the
  paper specifies (default ``sentence-transformers/all-MiniLM-L6-v2``), used
  as provided, without fine-tuning.
* :class:`HashingEncoder` - a deterministic bag-of-words feature-hashing
  encoder. It is **not** semantic; it exists so tests and offline demos run
  without downloading a model. Results computed with it must never be reported
  as Sentence-BERT results, and its ``model_id`` says so.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from typing import Mapping, Protocol

import numpy as np

from app.domain.semantic import cosine_clipped

log = logging.getLogger(__name__)


class Encoder(Protocol):
    model_id: str
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalised row per text (shape: len(texts) x dim)."""


def _normalize_rows(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class HashingEncoder:
    dim = 384
    _token = re.compile(r"[a-z0-9+#.]+")

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.model_id = f"hashing-bow-{dim}-v1 (NOT semantic; test/offline only)"

    def _index(self, token: str) -> tuple[int, float]:
        h = hashlib.blake2b(token.encode(), digest_size=8).digest()
        n = int.from_bytes(h, "little")
        return n % self.dim, 1.0 if (n >> 63) & 1 else -1.0

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for i, text in enumerate(texts):
            tokens = self._token.findall(text.lower())
            for tok in tokens + [a + " " + b for a, b in zip(tokens, tokens[1:])]:
                j, sign = self._index(tok)
                out[i, j] += sign
        return _normalize_rows(out)


class SentenceTransformerEncoder:
    def __init__(self, model_name: str, device: str = "cpu", batch_size: int = 32):
        self.model_name = model_name
        self.model_id = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # heavy import, loaded lazily

                log.info("loading sentence encoder %s", self.model_name)
                self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        vecs = model.encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float64)


def build_encoder(backend: str, model_name: str) -> Encoder:
    if backend == "sbert":
        return SentenceTransformerEncoder(model_name)
    if backend == "hashing":
        return HashingEncoder()
    raise ValueError(f"unknown EMBEDDING_BACKEND {backend!r} (expected 'sbert' or 'hashing')")


def validate_vector(vec, dim: int) -> list[float] | None:
    """Return a clean vector or None if missing/malformed (wrong dimension, non-finite)."""
    if vec is None:
        return None
    arr = np.asarray(vec, dtype=np.float64)
    if arr.ndim != 1 or arr.shape[0] != dim or not np.all(np.isfinite(arr)):
        return None
    return arr.tolist()


def semantic_scores(
    project_vec: list[float], profile_vecs: Mapping[str, list[float] | None]
) -> dict[str, float]:
    """f_sem per candidate. A candidate without usable profile text/vector gets
    0.0 (flagged by the caller) rather than being dropped."""
    return {cid: (cosine_clipped(v, project_vec) if v is not None else 0.0) for cid, v in profile_vecs.items()}


class InMemoryEmbeddingCache:
    """Text-keyed cache used by the research pipeline and tests."""

    def __init__(self, encoder: Encoder):
        self.encoder = encoder
        self._cache: dict[str, list[float]] = {}

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        missing = sorted({t for t in texts if t.strip() and self.key(t) not in self._cache})
        if missing:
            for t, v in zip(missing, self.encoder.encode(missing)):
                self._cache[self.key(t)] = v.tolist()
        return [self._cache.get(self.key(t)) if t.strip() else None for t in texts]
