from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from .common import Strict

Handle = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_]{3,24}$")]


class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    handle: Handle
    accept_terms: bool = Field(description="Consent to storing the account and profile data described on the privacy page")


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ConsentIn(Strict):
    research_participation: bool


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    handle: str
    role: Literal["student", "rater", "admin"]
    created_at: datetime
    consent: dict
    profile_complete: bool = False


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class DeleteAccountIn(Strict):
    password: str = Field(min_length=1, max_length=128)
    confirm: Literal["DELETE"]
