from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChildRef(BaseModel):
    id: UUID
    token: str


class ParseRequest(BaseModel):
    text: str = Field(max_length=1000)
    locale_hint: Literal["he", "en"]
    now: datetime
    timezone: Literal["Asia/Jerusalem"] = "Asia/Jerusalem"
    children: list[ChildRef]


class Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(max_length=200)
    child_ids: list[UUID]
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool
    remind_at: datetime | None = None


class ParseResponse(BaseModel):
    status: Literal["ready", "needs_clarification"]
    draft: Draft | None = None
    questions: list[str] = Field(default_factory=list)


class Suggestion(BaseModel):
    id: str
    text: str


class IdeasResponse(BaseModel):
    items: list[Suggestion]
    source: Literal["seed", "generated"]
