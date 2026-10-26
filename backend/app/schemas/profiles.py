from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, StringConstraints

from .common import RoleText, ShortText, Slot, Strict, WorkMode


class SkillIn(Strict):
    label: ShortText
    proficiency: int = Field(ge=1, le=4, description="1 learning, 2 one project, 3 several projects/lead, 4 advanced")
    kind: Literal["technical", "non_technical"] = "technical"


class ProjectSummaryIn(Strict):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] = ""
    contribution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)] = ""
    link: HttpUrl | None = None


class ProfileIn(Strict):
    year: int | None = Field(None, ge=1, le=6)
    branch: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    skills: list[SkillIn] = Field(default_factory=list, max_length=40)
    declared_absent: list[ShortText] = Field(default_factory=list, max_length=40,
                                             description="Skills the student explicitly does NOT have")
    primary_roles: list[RoleText] = Field(default_factory=list, max_length=3)
    secondary_roles: list[RoleText] = Field(default_factory=list, max_length=5)
    interests: list[ShortText] = Field(default_factory=list, max_length=15)
    projects: list[ProjectSummaryIn] = Field(default_factory=list, max_length=8)
    links: list[HttpUrl] = Field(default_factory=list, max_length=5)
    availability: list[Slot] | None = Field(None, max_length=21, description="null = not stated; [] = stated: none")
    weekly_hours: int | None = Field(None, ge=1, le=40)
    work_mode: WorkMode | None = None
    visible: bool = True


class SkillOut(BaseModel):
    label: str
    proficiency: int
    kind: str
    recognized: bool


class NormalizationNote(BaseModel):
    original: str
    canonical: str
    rule: str


class ProfileOut(BaseModel):
    user_id: str
    year: int | None
    branch: str | None
    skills: list[SkillOut]
    declared_absent: list[str]
    primary_roles: list[str]
    secondary_roles: list[str]
    interests: list[str]
    projects: list[dict]
    links: list[str]
    availability: list[str] | None
    weekly_hours: int | None
    work_mode: str | None
    visible: bool
    completion: dict
    updated_at: datetime | None
    normalization: list[NormalizationNote] = []


class PublicProfileOut(BaseModel):
    """What other students see. Availability slots are never exposed; only
    whether availability was stated."""

    user_id: str
    display_name: str
    handle: str
    year: int | None
    branch: str | None
    skills: list[SkillOut]
    primary_roles: list[str]
    secondary_roles: list[str]
    interests: list[str]
    projects: list[dict]
    links: list[str]
    weekly_hours: int | None
    work_mode: str | None
    availability_stated: bool
