"""/api/v1/invitations - inbox/outbox and responses."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser, Db
from app.schemas.social import InvitationOut
from app.services import teams

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("", response_model=list[InvitationOut])
async def list_invitations(user: CurrentUser, db: Db, box: Literal["received", "sent"] = "received",
                           status: Literal["pending", "accepted", "declined", "cancelled", "expired"] | None = Query(None)):
    """received = invitations to you + join requests to teams you created; sent = what you sent."""
    return await teams.list_invitations(db, user, box, status)


async def _respond(invitation_id: str, action, request: Request, user: dict, db) -> dict:
    inv = await teams.respond(db, request.app.state.notifier, user, invitation_id, action)
    return (await teams.invitations_out(db, [inv]))[0]


@router.post("/{invitation_id}/accept", response_model=InvitationOut, responses={403: {}, 404: {}, 409: {}})
async def accept(invitation_id: str, request: Request, user: CurrentUser, db: Db):
    return await _respond(invitation_id, "accept", request, user, db)


@router.post("/{invitation_id}/decline", response_model=InvitationOut, responses={403: {}, 404: {}, 409: {}})
async def decline(invitation_id: str, request: Request, user: CurrentUser, db: Db):
    return await _respond(invitation_id, "decline", request, user, db)


@router.post("/{invitation_id}/cancel", response_model=InvitationOut, responses={403: {}, 404: {}, 409: {}})
async def cancel(invitation_id: str, request: Request, user: CurrentUser, db: Db):
    return await _respond(invitation_id, "cancel", request, user, db)
