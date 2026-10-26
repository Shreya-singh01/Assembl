"""/api/v1/projects - discovery, creation, editing, team, recommendations, invitations."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request, status

from app.api.deps import CurrentUser, Db, OptionalUser, SettingsDep
from app.core.errors import forbidden
from app.schemas.projects import ProjectIn, ProjectListOut, ProjectOut, ProjectUpdateIn
from app.schemas.social import InvitationOut, InviteByHandleIn, InviteIn, JoinRequestIn
from app.services import messaging, recommendations, teams
from app.services import projects as svc
from app.services.auth import user_brief

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListOut)
async def list_projects(
    db: Db, user: OptionalUser,
    q: str | None = Query(None, max_length=80),
    opportunity_type: str | None = Query(None, max_length=20),
    skill: str | None = Query(None, max_length=60),
    status_: Literal["open", "closed"] | None = Query("open", alias="status"),
    mine: bool = False,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=10_000),
):
    docs, total = await svc.list_projects(db, user, q=q, opportunity_type=opportunity_type, skill=skill,
                                          status=status_, mine=mine, limit=limit, offset=offset)
    users = await svc.users_by_id(db, [m["user_id"] for d in docs for m in d["members"]])
    return {"items": [await svc.project_out(db, d, user, users) for d in docs], "total": total, "limit": limit,
            "offset": offset}


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectIn, user: CurrentUser, db: Db):
    doc = await svc.create_project(db, user, data)
    await messaging.sync_team_conversation(db, doc)
    return await svc.project_out(db, doc, user)


@router.get("/{project_id}", response_model=ProjectOut, responses={404: {}})
async def get_project(project_id: str, db: Db, user: OptionalUser):
    return await svc.project_out(db, await svc.get_project_for(db, project_id, user), user)


@router.put("/{project_id}", response_model=ProjectOut, responses={403: {}, 404: {}, 409: {}})
async def update_project(project_id: str, data: ProjectUpdateIn, user: CurrentUser, db: Db):
    return await svc.project_out(db, await svc.update_project(db, user, project_id, data), user)


@router.get("/{project_id}/coverage")
async def get_coverage(project_id: str, user: CurrentUser, db: Db):
    """Importance-weighted requirement coverage of the current team (Eqs. 2-3)."""
    return await recommendations.team_coverage(db, user, project_id)


@router.get("/{project_id}/recommendations", responses={403: {}, 404: {}})
async def get_recommendations(project_id: str, request: Request, user: CurrentUser, db: Db, settings: SettingsDep,
                              limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Ranked candidates for the team as it currently stands (creator only)."""
    return await recommendations.recommend(db, request.app.state.embedding_store, user, project_id, limit=limit,
                                           offset=offset, timeout_s=settings.recommendation_timeout_s)


@router.post("/{project_id}/invitations", response_model=InvitationOut, status_code=201, responses={403: {}, 404: {}, 409: {}})
async def invite(project_id: str, data: InviteIn, request: Request, user: CurrentUser, db: Db):
    inv = await teams.invite(db, request.app.state.notifier, user, project_id, data.candidate_id, data.role, data.message)
    return (await teams.invitations_out(db, [inv]))[0]


@router.post("/{project_id}/invitations/by-handle", response_model=InvitationOut, status_code=201)
async def invite_by_handle(project_id: str, data: InviteByHandleIn, request: Request, user: CurrentUser, db: Db):
    """Invite a known student (e.g. an existing teammate) by handle."""
    inv = await teams.invite_by_handle(db, request.app.state.notifier, user, project_id, data.handle, data.role, data.message)
    return (await teams.invitations_out(db, [inv]))[0]


@router.post("/{project_id}/join-requests", response_model=InvitationOut, status_code=201)
async def request_to_join(project_id: str, data: JoinRequestIn, request: Request, user: CurrentUser, db: Db):
    inv = await teams.request_to_join(db, request.app.state.notifier, user, project_id, data.role, data.message)
    return (await teams.invitations_out(db, [inv]))[0]


@router.get("/{project_id}/invitations", response_model=list[InvitationOut])
async def project_invitations(project_id: str, user: CurrentUser, db: Db):
    project = await svc.get_project_for(db, project_id, user)
    if project["owner_id"] != user["_id"]:
        raise forbidden("Only the project creator can see the team's invitations")
    invs = [i async for i in db.invitations.find({"project_id": project["_id"]}).sort("created_at", -1).limit(200)]
    return await teams.invitations_out(db, invs)


@router.delete("/{project_id}/members/{member_id}", response_model=ProjectOut, responses={403: {}, 404: {}})
async def remove_member(project_id: str, member_id: str, request: Request, user: CurrentUser, db: Db):
    """Creator removes a member, or a member removes themself (leaves)."""
    doc = await teams.remove_member(db, request.app.state.notifier, user, project_id, member_id)
    return await svc.project_out(db, doc, user)


@router.get("/{project_id}/history")
async def membership_history(project_id: str, user: CurrentUser, db: Db):
    project = await svc.get_project_for(db, project_id, user)
    if not svc.is_member(project, user["_id"]):
        raise forbidden("Only team members can see the membership history")
    users = await svc.users_by_id(db, [h.get("user_id") for h in project.get("history", [])] +
                                  [h.get("by") for h in project.get("history", [])])
    return [{"at": h["at"], "type": h["type"], "user": user_brief(users.get(h.get("user_id"))) if h.get("user_id") else None,
             "by": user_brief(users.get(h.get("by"))) if h.get("by") else None} for h in project.get("history", [])]
