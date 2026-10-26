"""ASGI entry point: ``uvicorn app.main:app``.

``app`` is the Socket.IO ASGI app wrapping the FastAPI app, so REST
(/api/v1/...) and real-time (/socket.io/) share one process and one port.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import OriginCheckMiddleware
from app.api.routes import auth, conversations, dashboard, invitations, profiles, projects, research
from app.core.config import Settings, get_settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.ratelimit import build_rate_limiter
from app.db.mongo import create_client, ensure_indexes, is_memory_client
from app.domain.models import DomainValidationError
from app.services.embedding_store import EmbeddingStore
from app.services.embeddings import Encoder, build_encoder
from app.websocket.notifier import Notifier
from app.websocket.server import create_sio, register_handlers

log = logging.getLogger("assembl")


def create_app(settings: Settings | None = None, *, encoder: Encoder | None = None, db=None) -> socketio.ASGIApp:
    settings = settings or get_settings()
    problems = settings.check_production()
    if problems:
        raise RuntimeError("unsafe production configuration: " + "; ".join(problems))

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        client = None
        if db is None:
            client = create_client(settings.mongodb_url)
            api.state.db = client[settings.mongodb_db]
            await ensure_indexes(api.state.db, memory=is_memory_client(client))
        api.state.embedding_store = EmbeddingStore(api.state.db, api.state.encoder)
        if os.environ.get("SEED_DEMO") == "1" and settings.environment != "production":
            from app.seed import seed

            log.info("demo seed: %s", await seed(api.state.db))
        warm = None
        if getattr(api.state.encoder, "loaded", True) is False:
            # load the sentence encoder in the background so the first recommendation is fast
            warm = asyncio.get_running_loop().run_in_executor(None, lambda: api.state.encoder.dim)
        yield
        if warm is not None and not warm.done():
            warm.cancel()
        if client is not None:
            client.close()

    api = FastAPI(
        title="Assembl API",
        version="0.1.0",
        description="Team-aware candidate recommendation for student teams. "
                    "Ranking scores are relative values for one request, not probabilities of team success.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    api.state.settings = settings
    if db is not None:
        api.state.db = db
    api.state.encoder = encoder or build_encoder(settings.embedding_backend, settings.embedding_model)
    api.state.rate_limiter = build_rate_limiter(settings.redis_url)

    api.add_middleware(OriginCheckMiddleware, allowed=settings.cors_origin_list)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        max_age=600,
    )
    api.add_middleware(RequestContextMiddleware)

    @api.exception_handler(DomainValidationError)
    async def _domain_error(_: Request, exc: DomainValidationError):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @api.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = [{"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse({"detail": "Invalid request", "errors": errors}, status_code=422)

    @api.exception_handler(TimeoutError)
    async def _timeout(_: Request, exc: TimeoutError):
        return JSONResponse({"detail": "The operation took too long; please retry"}, status_code=503)

    @api.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    for r in (auth.router, profiles.router, projects.router, invitations.router, conversations.router,
              research.router, dashboard.router, dashboard.health):
        api.include_router(r, prefix="/api/v1")

    sio = create_sio(settings)
    register_handlers(sio, api)
    api.state.sio = sio
    api.state.notifier = Notifier(sio)
    asgi = socketio.ASGIApp(sio, other_asgi_app=api, socketio_path="socket.io")
    asgi.fastapi = api  # convenient handle for tests
    return asgi


def _default_app():
    settings = get_settings()
    configure_logging("INFO" if settings.environment != "development" else "INFO")
    return create_app(settings)


app = _default_app()
