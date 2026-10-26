"""Fixed-window rate limiting with an optional Redis backend.

Redis is used only when ``REDIS_URL`` is set and reachable. If it is missing
or fails at runtime the limiter degrades to an in-process counter (correct
for a single instance) and logs a warning, so a Redis outage never takes the
API down.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

log = logging.getLogger(__name__)


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        window = int(time.time() // window_s)
        w, n = self._hits[key]
        n = n + 1 if w == window else 1
        self._hits[key] = (window, n)
        if len(self._hits) > 50_000:  # bound memory
            self._hits.clear()
        return n <= limit

    async def reset(self, key: str) -> None:
        self._hits.pop(key, None)


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis  # optional dependency

        self._redis = aioredis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
        self._fallback = MemoryRateLimiter()

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        try:
            k = f"rl:{key}:{int(time.time() // window_s)}"
            pipe = self._redis.pipeline()
            pipe.incr(k)
            pipe.expire(k, window_s)
            n, _ = await pipe.execute()
            return int(n) <= limit
        except Exception as exc:  # noqa: BLE001
            log.warning("redis rate limiter unavailable, using in-process fallback: %s", exc.__class__.__name__)
            return await self._fallback.hit(key, limit, window_s)

    async def reset(self, key: str) -> None:
        await self._fallback.reset(key)


def build_rate_limiter(redis_url: str):
    if redis_url:
        try:
            return RedisRateLimiter(redis_url)
        except ImportError:
            log.warning("REDIS_URL set but the redis package is not installed; using in-process rate limiting")
    return MemoryRateLimiter()
