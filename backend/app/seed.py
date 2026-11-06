"""Small synthetic demo dataset for local runs (SEED_DEMO=1, or python -m app.seed).

A thin wrapper around app.synthdata with a small size, so the in-memory demo
starts quickly. For the full dataset use ``python -m app.synthdata load``.
Everything is synthetic and labelled (see app/synthdata/__init__.py).
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.mongo import create_client, ensure_indexes, is_memory_client
from app.synthdata import DEMO_DOMAIN, DEMO_PASSWORD, platform


async def seed(db, n_students: int = 24, n_projects: int = 6) -> dict:
    if get_settings().environment == "production":
        raise RuntimeError("refusing to seed demo data in production")
    if await platform.demo_present(db):
        return {"skipped": "demo data already present"}
    await platform.load(db, students=n_students, projects=n_projects, direct_chats=5, research=False)
    return {"students": n_students, "projects": n_projects,
            "demo_login": f"aarav_demo0@{DEMO_DOMAIN} / {DEMO_PASSWORD}"}


async def _main() -> None:
    s = get_settings()
    client = create_client(s.mongodb_url)
    db = client[s.mongodb_db]
    await ensure_indexes(db, memory=is_memory_client(client))
    print(await seed(db))
    client.close()


if __name__ == "__main__":
    asyncio.run(_main())
