"""Persistent embedding cache.

Profile embeddings live in ``embeddings`` keyed by (user_id, model_id) and
store the SHA-256 of the exact text they were computed from plus the text
template version. A cached vector is reused only when model, template and text
hash all match and the vector has the encoder's dimension; otherwise it is
recomputed. Project embeddings are stored on the project document under the
same rules. Deleting an account deletes its embeddings.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

import anyio

from app.domain.semantic import TEXT_TEMPLATE_VERSION, profile_text, project_text
from app.services.auth import now
from app.services.embeddings import Encoder, semantic_scores, validate_vector
from app.services.profiles import to_domain
from app.services.projects import to_spec


def text_hash(text: str) -> str:
    return hashlib.sha256(f"{TEXT_TEMPLATE_VERSION}\n{text}".encode()).hexdigest()


class EmbeddingStore:
    def __init__(self, db, encoder: Encoder):
        self.db = db
        self.encoder = encoder

    async def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = await anyio.to_thread.run_sync(self.encoder.encode, texts)
        return [v.tolist() for v in vecs]

    async def profile_vectors(self, docs: Iterable[dict]) -> dict[str, list[float] | None]:
        docs = list(docs)
        texts = {d["_id"]: d.get("text") or profile_text(to_domain(d)) for d in docs}
        model = self.encoder.model_id
        cached = {
            c["user_id"]: c
            async for c in self.db.embeddings.find({"user_id": {"$in": list(texts)}, "model_id": model})
        }
        out: dict[str, list[float] | None] = {}
        todo: list[tuple] = []
        for uid, text in texts.items():
            if not text.strip():
                out[str(uid)] = None  # nothing to embed; f_sem = 0 and flagged
                continue
            c = cached.get(uid)
            vec = None
            if c and c.get("text_hash") == text_hash(text) and self.encoder.dim:
                vec = validate_vector(c.get("vector"), self.encoder.dim)
            if vec is None:
                todo.append((uid, text))
            else:
                out[str(uid)] = vec
        if todo:
            vecs = await self._encode([t for _, t in todo])
            for (uid, text), vec in zip(todo, vecs):
                out[str(uid)] = vec
                await self.db.embeddings.replace_one(
                    {"user_id": uid, "model_id": model},
                    {"user_id": uid, "model_id": model, "text_hash": text_hash(text), "template": TEXT_TEMPLATE_VERSION,
                     "dim": len(vec), "vector": vec, "created_at": now()},
                    upsert=True,
                )
        return out

    async def project_vector(self, project_doc: dict) -> list[float]:
        text = project_text(to_spec(project_doc))
        cached = project_doc.get("embedding") or {}
        if (cached.get("model_id") == self.encoder.model_id and cached.get("text_hash") == text_hash(text)
                and self.encoder.dim and validate_vector(cached.get("vector"), self.encoder.dim)):
            return cached["vector"]
        vec = (await self._encode([text]))[0]
        await self.db.projects.update_one(
            {"_id": project_doc["_id"]},
            {"$set": {"embedding": {"model_id": self.encoder.model_id, "text_hash": text_hash(text), "vector": vec}}},
        )
        return vec

    async def semantic(self, project_doc: dict, candidate_docs: list[dict]) -> dict[str, float]:
        pvec = await self.project_vector(project_doc)
        return semantic_scores(pvec, await self.profile_vectors(candidate_docs))
