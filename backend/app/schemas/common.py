from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
PERIODS = ("am", "pm", "eve")
SLOT_RE = re.compile(rf"^({'|'.join(DAYS)})-({'|'.join(PERIODS)})$")
WorkMode = Literal["online", "offline", "hybrid"]
OpportunityType = Literal["hackathon", "academic", "research", "startup", "competition", "other"]


def _slot(v: str) -> str:
    if not SLOT_RE.match(v):
        raise ValueError("availability slots look like 'mon-eve' (day: mon..sun, period: am/pm/eve)")
    return v


Slot = Annotated[str, AfterValidator(_slot)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
RoleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(BaseModel):
    total: int
    limit: int
    offset: int
