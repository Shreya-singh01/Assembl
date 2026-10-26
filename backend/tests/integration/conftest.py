"""API test harness: in-memory MongoDB + deterministic hashing encoder.

Never points at a real database.
"""

from __future__ import annotations

import itertools

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient

from app.core.config import Settings
from app.db.mongo import ensure_indexes
from app.main import create_app
from app.services.embeddings import HashingEncoder

_counter = itertools.count()


@pytest.fixture
async def app_and_db():
    client = AsyncMongoMockClient(tz_aware=True)
    db = client[f"test_{next(_counter)}"]
    await ensure_indexes(db, memory=True)
    settings = Settings(environment="test", mongodb_url="memory://", embedding_backend="hashing",
                        cors_origins="http://localhost:5173", admin_emails="admin@example.edu",
                        login_rate_limit=5, message_rate_limit=5)
    asgi = create_app(settings, encoder=HashingEncoder(), db=db)
    api = asgi.fastapi
    async with api.router.lifespan_context(api):
        yield asgi, db


class Api:
    """Thin client wrapper that remembers the CSRF token like the frontend does."""

    def __init__(self, client: httpx.AsyncClient):
        self.c = client
        self.csrf: str | None = None
        self.user: dict | None = None

    def _h(self, extra=None):
        h = {"X-CSRF-Token": self.csrf} if self.csrf else {}
        return {**h, **(extra or {})}

    async def get(self, url, **kw):
        return await self.c.get(url, headers=self._h(kw.pop("headers", None)), **kw)

    async def post(self, url, json=None, **kw):
        return await self.c.post(url, json=json, headers=self._h(kw.pop("headers", None)), **kw)

    async def put(self, url, json=None, **kw):
        return await self.c.put(url, json=json, headers=self._h(kw.pop("headers", None)), **kw)

    async def delete(self, url, **kw):
        return await self.c.delete(url, headers=self._h(kw.pop("headers", None)), **kw)

    async def register(self, name: str, email: str | None = None):
        r = await self.post("/api/v1/auth/register", {
            "email": email or f"{name}@example.edu", "password": "correct horse battery", "display_name": name.title(),
            "handle": name, "accept_terms": True})
        assert r.status_code == 201, r.text
        self.csrf, self.user = r.json()["csrf_token"], r.json()["user"]
        return self


@pytest.fixture
def make_client(app_and_db):
    asgi, _ = app_and_db
    clients: list[httpx.AsyncClient] = []

    def make() -> Api:
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi), base_url="http://testserver")
        clients.append(c)
        return Api(c)

    yield make


@pytest.fixture
def db(app_and_db):
    return app_and_db[1]


def profile(skills: dict[str, int], **kw) -> dict:
    base = {"year": 2, "branch": "CSE", "skills": [{"label": k, "proficiency": v} for k, v in skills.items()],
            "primary_roles": [], "interests": [], "availability": None, "visible": True}
    base.update(kw)
    return base


def project_payload(**kw) -> dict:
    base = {
        "title": "Placement prep platform",
        "description": "A placement-preparation web application with mock interviews and analytics.",
        "opportunity_type": "hackathon",
        "requirements": [
            {"skill": "React", "importance": 2, "desired_proficiency": 3},
            {"skill": "Machine Learning", "importance": 2, "desired_proficiency": 3},
            {"skill": "nodejs", "importance": 3, "desired_proficiency": 3},
            {"skill": "postgres", "importance": 3, "desired_proficiency": 2},
        ],
        "target_size": 4,
        "creator_role": "Frontend",
        "vacant_roles": ["Backend", "ML"],
    }
    base.update(kw)
    return base
