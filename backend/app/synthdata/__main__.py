"""Synthetic data CLI. Reads MONGODB_URL / MONGODB_DB from the environment or backend/.env.

    python -m app.synthdata load      [--students 300] [--projects 40] [--reset] [--encoder sbert|hashing]
    python -m app.synthdata verify    rank every synthetic project and check each case behaves as designed
    python -m app.synthdata summary   counts of what is in the database
    python -m app.synthdata clear     delete every synthetic record (and nothing else)

Refuses to write synthetic data into a database named "assembl" (reserved for
real students) unless --allow-real-db is given, and never runs in production.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.db.mongo import create_client, ensure_indexes, is_memory_client
from app.services.auth import now
from app.services.embeddings import build_encoder

from . import platform

REAL_DB_NAMES = {"assembl"}


def _guard(settings, allow_real: bool) -> None:
    if settings.environment == "production":
        sys.exit("refusing: ENVIRONMENT=production")
    if settings.mongodb_db in REAL_DB_NAMES and not allow_real:
        sys.exit(f"refusing to write synthetic data into '{settings.mongodb_db}' (reserved for real students); "
                 "use MONGODB_DB=assembl_demo or pass --allow-real-db")


async def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.synthdata")
    ap.add_argument("command", choices=["load", "verify", "summary", "clear"])
    ap.add_argument("--students", type=int, default=300)
    ap.add_argument("--projects", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--reset", action="store_true", help="clear existing synthetic data before loading")
    ap.add_argument("--no-research", action="store_true")
    ap.add_argument("--encoder", choices=["sbert", "hashing"])
    ap.add_argument("--allow-real-db", action="store_true")
    a = ap.parse_args(argv)

    s = get_settings()
    client = create_client(s.mongodb_url)
    db = client[s.mongodb_db]
    print(f"database: {s.mongodb_db} ({'in-memory' if is_memory_client(client) else 'MongoDB server'})")
    try:
        if a.command in ("load", "clear"):
            _guard(s, a.allow_real_db)
        await ensure_indexes(db, memory=is_memory_client(client))
        encoder = build_encoder(a.encoder or s.embedding_backend, s.embedding_model)

        if a.command == "clear":
            print(json.dumps(await platform.clear(db), indent=1))
        elif a.command == "summary":
            print(json.dumps(await platform.summary(db), indent=1, default=str))
        elif a.command == "load":
            if await platform.demo_present(db):
                if not a.reset:
                    sys.exit("synthetic data already present; run with --reset to replace it")
                print("cleared:", await platform.clear(db))
            stats = await platform.load(db, students=a.students, projects=a.projects, seed=a.seed,
                                        research=not a.no_research, encoder=encoder)
            print("loaded:", json.dumps({k: v for k, v in stats.items() if k != "project_cases"}, indent=1))
            a.command = "verify"
        if a.command == "verify":
            results = await platform.verify(db, encoder)
            failed = [r for r in results if any(not c["passed"] for c in r["checks"])]
            for r in results:
                marks = " ".join(("PASS " if c["passed"] else "FAIL ") + c["check"] for c in r["checks"]) or "-"
                print(f"{r['case']:<34} members={r['members']} status={r['status']:<22} eligible={r['eligible']:<4} "
                      f"omitted={','.join(r['omitted']) or '-':<12} {marks}")
            await db.synthetic_meta.replace_one({"_id": "last_verification"},
                                                {"_id": "last_verification", "at": now(), "encoder": encoder.model_id,
                                                 "results": results, "failed": len(failed)}, upsert=True)
            print(f"\n{len(results)} projects ranked; {sum(len(r['checks']) for r in results)} case checks; "
                  f"{len(failed)} project(s) with a failed check")
            print(json.dumps(await platform.summary(db), indent=1, default=str))
            if failed:
                sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
