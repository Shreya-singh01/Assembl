import os

import numpy as np
import pytest

from app.core.ratelimit import MemoryRateLimiter, build_rate_limiter
from app.core.security import hash_password, new_token, token_digest, verify_password
from app.services.embeddings import HashingEncoder, InMemoryEmbeddingCache, validate_vector


async def test_memory_rate_limiter_window():
    rl = MemoryRateLimiter()
    assert [await rl.hit("k", 2, 60) for _ in range(3)] == [True, True, False]


async def test_unreachable_redis_degrades_to_memory():
    rl = build_rate_limiter("redis://127.0.0.1:1/0")
    assert await rl.hit("k", 1, 60) is True
    assert await rl.hit("k", 1, 60) is False


def test_password_hashing():
    h = hash_password("correct horse battery")
    assert h.startswith("scrypt$") and "correct" not in h
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "garbage")


def test_session_tokens_are_random_and_stored_hashed():
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 40
    assert token_digest(a) != a and len(token_digest(a)) == 64


def test_hashing_encoder_deterministic_and_normalised():
    enc = HashingEncoder()
    a = enc.encode(["React and Node.js developer", ""])
    b = enc.encode(["React and Node.js developer", ""])
    assert np.array_equal(a, b)
    assert np.linalg.norm(a[0]) == pytest.approx(1.0)
    assert np.linalg.norm(a[1]) == 0.0


def test_embedding_cache_skips_empty_text():
    cache = InMemoryEmbeddingCache(HashingEncoder())
    vecs = cache.embed_many(["hello world", "   "])
    assert vecs[0] is not None and vecs[1] is None


def test_validate_vector():
    assert validate_vector([0.1, 0.2], 2) == [0.1, 0.2]
    assert validate_vector([0.1], 2) is None
    assert validate_vector([float("nan"), 0.0], 2) is None
    assert validate_vector(None, 2) is None


@pytest.mark.sbert
@pytest.mark.skipif(os.environ.get("ASSEMBL_TEST_SBERT") != "1", reason="set ASSEMBL_TEST_SBERT=1 to load the real model")
def test_real_sentence_bert_semantics():
    from app.domain.semantic import cosine_clipped
    from app.services.embeddings import SentenceTransformerEncoder

    enc = SentenceTransformerEncoder("sentence-transformers/all-MiniLM-L6-v2")
    v = enc.encode(["REST API design", "backend web services", "watercolour painting of flowers"])
    assert enc.dim == 384 and v.shape == (3, 384)
    related = cosine_clipped(v[0], v[1])
    unrelated = cosine_clipped(v[0], v[2])
    assert 0.0 <= unrelated < related <= 1.0
    assert np.allclose(v, enc.encode(["REST API design", "backend web services", "watercolour painting of flowers"]))
