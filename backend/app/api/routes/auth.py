"""/api/v1/auth - registration, login, logout, current session, account deletion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, Db, SettingsDep
from app.core.config import Settings
from app.schemas.auth import ConsentIn, DeleteAccountIn, LoginIn, RegisterIn, SessionOut, UserOut
from app.services import account
from app.services import auth as svc
from app.services.profiles import completion

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name, token, max_age=settings.session_ttl_hours * 3600, httponly=True,
        secure=settings.cookie_secure, samesite=settings.cookie_samesite, domain=settings.cookie_domain, path="/",
    )


async def _profile_ready(db, user_id) -> bool:
    return completion(await db.profiles.find_one({"_id": user_id}))["ready_for_matching"]


@router.post("/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "E-mail or handle already in use"}})
async def register(data: RegisterIn, request: Request, response: Response, db: Db, settings: SettingsDep):
    if not data.accept_terms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please accept the data-use terms to create an account")
    limiter = request.app.state.rate_limiter
    ip = request.client.host if request.client else "?"
    if not await limiter.hit(f"register:{ip}", 20, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many registrations from this address; try later")
    user = await svc.register(db, settings, data.email, data.password, data.display_name, data.handle)
    token, session = await svc.create_session(db, settings, user["_id"])
    _set_cookie(response, settings, token)
    return {"user": svc.user_out(user), "csrf_token": session["csrf_token"]}


@router.post("/login", response_model=SessionOut, responses={401: {}, 429: {}})
async def login(data: LoginIn, request: Request, response: Response, db: Db, settings: SettingsDep):
    ip = request.client.host if request.client else "?"
    key = f"login:{ip}:{data.email.lower()}"
    if not await request.app.state.rate_limiter.hit(key, settings.login_rate_limit, settings.login_rate_window_s):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts; wait a few minutes")
    user = await svc.authenticate(db, data.email, data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect e-mail or password")
    # rotate: a fresh session id on every login (prevents session fixation)
    await svc.destroy_session(db, request.cookies.get(settings.session_cookie_name))
    token, session = await svc.create_session(db, settings, user["_id"])
    _set_cookie(response, settings, token)
    return {"user": svc.user_out(user, await _profile_ready(db, user["_id"])), "csrf_token": session["csrf_token"]}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser, request: Request, response: Response, db: Db, settings: SettingsDep):
    await svc.destroy_session(db, request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)


@router.get("/me", response_model=SessionOut, responses={401: {}})
async def me(user: CurrentUser, request: Request, db: Db):
    return {"user": svc.user_out(user, await _profile_ready(db, user["_id"])),
            "csrf_token": request.state.session["csrf_token"]}


@router.put("/consent", response_model=UserOut)
async def update_consent(data: ConsentIn, user: CurrentUser, db: Db):
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"consent.research_participation": data.research_participation}})
    user = await db.users.find_one({"_id": user["_id"]})
    return svc.user_out(user, await _profile_ready(db, user["_id"]))


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT, responses={401: {}})
async def delete_account(data: DeleteAccountIn, user: CurrentUser, request: Request, response: Response, db: Db,
                         settings: SettingsDep):
    if not await svc.authenticate(db, user["email"], data.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")
    await account.delete_account(db, request.app.state.notifier, user)
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)
