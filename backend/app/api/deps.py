"""Request dependencies: database, current user, CSRF and role checks.

CSRF: every state-changing request from a signed-in user must carry the
session's CSRF token in ``X-CSRF-Token`` (synchroniser-token pattern; the
token is returned by /auth/login and /auth/me and kept in memory by the
client). In addition, :class:`OriginCheckMiddleware` rejects unsafe requests
whose ``Origin`` is not an allowed frontend origin.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.core.security import constant_time_equals
from app.services import auth as auth_service

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    return request.app.state.db


Db = Annotated[object, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def current_user(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    found = await auth_service.session_user(request.app.state.db, token)
    if not found:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    session, user = found
    if request.method in UNSAFE and not constant_time_equals(request.headers.get("x-csrf-token"), session["csrf_token"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    request.state.session = session
    return user


async def optional_user(request: Request) -> dict | None:
    settings: Settings = request.app.state.settings
    found = await auth_service.session_user(request.app.state.db, request.cookies.get(settings.session_cookie_name))
    return found[1] if found else None


CurrentUser = Annotated[dict, Depends(current_user)]
OptionalUser = Annotated[dict | None, Depends(optional_user)]


async def require_admin(user: CurrentUser) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


async def require_rater(user: CurrentUser) -> dict:
    if user.get("role") not in ("rater", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rater access required")
    return user


AdminUser = Annotated[dict, Depends(require_admin)]
RaterUser = Annotated[dict, Depends(require_rater)]


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-site state-changing requests (defence in depth next to the
    CSRF token and SameSite cookies). Requests without an Origin header (e.g.
    server-to-server tools) are allowed; browsers always send it on
    cross-origin POSTs."""

    def __init__(self, app, allowed: list[str]):
        super().__init__(app)
        self.allowed = set(allowed)

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in UNSAFE and origin:
            own = f"{request.url.scheme}://{request.url.netloc}"
            if origin.rstrip("/") not in self.allowed and origin.rstrip("/") != own:
                return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
        return await call_next(request)
