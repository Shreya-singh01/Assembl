"""MongoDB connection lifecycle and indexes.

``MONGODB_URL=memory://`` selects mongomock-motor (in-process, non-persistent)
for tests and zero-install demos. Every other URL goes to Motor.

Team-size safety does not rely on multi-document transactions: joining a team
is a single conditional ``find_one_and_update`` on the project document (see
app/services/teams.py), which MongoDB applies atomically.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING, IndexModel

log = logging.getLogger(__name__)


def create_client(url: str):
    if url.startswith("memory://"):
        from mongomock_motor import AsyncMongoMockClient

        log.warning("using in-memory MongoDB mock: data is NOT persisted")
        return AsyncMongoMockClient(tz_aware=True)
    from motor.motor_asyncio import AsyncIOMotorClient

    return AsyncIOMotorClient(url, tz_aware=True, serverSelectionTimeoutMS=5000, uuidRepresentation="standard")


INDEXES: dict[str, list[IndexModel]] = {
    "users": [
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("handle_key", ASCENDING)], unique=True),
    ],
    "sessions": [
        IndexModel([("user_id", ASCENDING)]),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
    ],
    "profiles": [
        IndexModel([("visible", ASCENDING)]),
    ],
    "embeddings": [
        IndexModel([("user_id", ASCENDING), ("model_id", ASCENDING)], unique=True),
    ],
    "projects": [
        IndexModel([("owner_id", ASCENDING)]),
        IndexModel([("status", ASCENDING), ("opportunity_type", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("members.user_id", ASCENDING)]),
        IndexModel([("event_key", ASCENDING)], sparse=True),
    ],
    "invitations": [
        IndexModel([("project_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("candidate_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("from_user", ASCENDING), ("status", ASCENDING)]),
        IndexModel(
            [("project_id", ASCENDING), ("candidate_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"status": "pending"},
            name="one_pending_per_candidate",
        ),
    ],
    "conversations": [
        IndexModel([("participant_ids", ASCENDING), ("last_message_at", DESCENDING)]),
        IndexModel([("direct_key", ASCENDING)], unique=True, sparse=True),
        IndexModel([("project_id", ASCENDING)], sparse=True),
    ],
    "messages": [
        IndexModel([("conversation_id", ASCENDING), ("created_at", DESCENDING)]),
        # client_id is always set (generated server-side when the client sends none)
        IndexModel([("conversation_id", ASCENDING), ("sender_id", ASCENDING), ("client_id", ASCENDING)],
                   unique=True, name="idempotent_send"),
    ],
    "research_scenarios": [IndexModel([("provenance", ASCENDING)])],
    "judgments": [
        IndexModel([("scenario_id", ASCENDING), ("candidate_id", ASCENDING), ("rater_id", ASCENDING)], unique=True),
    ],
    "evaluation_runs": [IndexModel([("created_at", DESCENDING)])],
}


def is_memory_client(client) -> bool:
    return type(client).__module__.startswith("mongomock")


async def ensure_indexes(db, memory: bool = False) -> None:
    """Create indexes. The in-memory mock ignores partial filters (it would turn
    "one *pending* invitation per candidate" into "one invitation ever"), so
    partial indexes are skipped there; services also enforce that rule in code."""
    for name, models in INDEXES.items():
        if memory:
            models = [m for m in models if "partialFilterExpression" not in m.document]
        if models:
            await db[name].create_indexes(models)
