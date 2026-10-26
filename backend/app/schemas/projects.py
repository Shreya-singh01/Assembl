from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .common import OpportunityType, RoleText, ShortText, Strict, WorkMode


class RequirementIn(Strict):
    skill: ShortText
    importance: int = Field(ge=1, le=3, description="1 useful, 2 important, 3 essential (ranking weight)")
    desired_proficiency: int = Field(ge=1, le=4)
    mandatory: bool = Field(False, description="Eligibility rule: every new member must state at least the desired proficiency")


class ProjectIn(Strict):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=4000)]
    opportunity_type: OpportunityType
    event_key: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=80)] | None = Field(
        None, description="Projects for the same event share a key; a student can be on only one team per event")
    requirements: list[RequirementIn] = Field(min_length=1, max_length=20)
    target_size: int = Field(ge=2, le=12)
    creator_role: RoleText | None = None
    vacant_roles: list[RoleText] = Field(default_factory=list, max_length=8)
    allowed_years: list[int] | None = Field(None, max_length=6)
    role_mandatory: bool = False
    synchronous: bool = False
    min_shared_slots: int = Field(0, ge=0, le=21)
    availability_policy: Literal["all", "majority"] = "all"
    availability_mandatory: bool = False
    weekly_hours: int | None = Field(None, ge=1, le=40)
    work_mode: WorkMode | None = None
    unverifiable_policy: Literal["exclude", "include"] = "exclude"
    visibility: Literal["public", "private"] = "public"

    @model_validator(mode="after")
    def _consistency(self):
        if self.allowed_years is not None and not all(1 <= y <= 6 for y in self.allowed_years):
            raise ValueError("allowed years must be between 1 and 6")
        if self.synchronous and self.min_shared_slots < 1:
            raise ValueError("synchronous teams must request at least one shared weekly slot")
        if self.availability_mandatory and not self.synchronous:
            raise ValueError("mandatory shared availability requires synchronous work")
        if self.role_mandatory and not self.vacant_roles:
            raise ValueError("a mandatory role rule needs at least one vacant role")
        return self


class ProjectUpdateIn(ProjectIn):
    status: Literal["open", "closed"] = "open"
    version: int = Field(ge=0, description="Version you edited; a stale version is rejected with 409")


class MemberOut(BaseModel):
    user_id: str
    display_name: str
    handle: str
    role: str | None
    joined_at: datetime
    is_owner: bool


class ProjectOut(BaseModel):
    id: str
    owner_id: str
    title: str
    description: str
    opportunity_type: str
    event_key: str | None
    requirements: list[dict]
    target_size: int
    open_positions: int
    vacant_roles: list[str]
    allowed_years: list[int] | None
    role_mandatory: bool
    synchronous: bool
    min_shared_slots: int
    availability_policy: str
    availability_mandatory: bool
    weekly_hours: int | None
    work_mode: str | None
    unverifiable_policy: str
    visibility: str
    status: str
    members: list[MemberOut]
    created_at: datetime
    updated_at: datetime
    version: int
    viewer: dict = Field(default_factory=dict, description="The caller's relationship to the project")


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int
    limit: int
    offset: int
