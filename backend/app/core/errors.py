"""Application errors and helpers shared by services and routes."""

from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status


def not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def forbidden(detail: str = "You do not have permission to do that") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def oid(value: str, what: str = "Resource") -> ObjectId:
    """Parse a client-supplied id. Malformed ids are reported as 404, the same
    as ids that do not exist, so ids cannot be probed."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise not_found(what) from None
