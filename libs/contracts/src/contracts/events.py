"""Redis stream payloads. Unknown fields are ignored by consumers."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    v: int = 1


class ContactUpdated(_Event):
    type: Literal["family.contact_updated"] = "family.contact_updated"
    family_id: UUID
    email: str
    locale: Literal["he", "en"]
    request_id: str | None = None


class ContactRemoved(_Event):
    type: Literal["family.contact_removed"] = "family.contact_removed"
    family_id: UUID
    request_id: str | None = None


class EventUpserted(_Event):
    type: Literal["calendar.event_upserted"] = "calendar.event_upserted"
    event_id: UUID
    family_id: UUID
    generation: int
    title: str
    starts_at: datetime
    remind_at: datetime | None
    locale: Literal["he", "en"]
    request_id: str | None = None


class EventCancelled(_Event):
    type: Literal["calendar.event_cancelled"] = "calendar.event_cancelled"
    event_id: UUID
    family_id: UUID
    generation: int
    request_id: str | None = None


StreamMessage = ContactUpdated | ContactRemoved | EventUpserted | EventCancelled

STREAM_TYPES: dict[str, type[_Event]] = {
    "family.contact_updated": ContactUpdated,
    "family.contact_removed": ContactRemoved,
    "calendar.event_upserted": EventUpserted,
    "calendar.event_cancelled": EventCancelled,
}


def parse_event(event_type: str, payload: dict[str, object]) -> StreamMessage:
    model = STREAM_TYPES.get(event_type)
    if model is None:
        raise ValueError(f"unknown event type: {event_type}")
    body = dict(payload)
    body["type"] = event_type
    parsed = model.model_validate(body)
    if not isinstance(parsed, (ContactUpdated, ContactRemoved, EventUpserted, EventCancelled)):
        raise TypeError(event_type)
    return parsed


class StreamEntry(BaseModel):
    """Fields on the Redis stream entry. `json` is the payload document."""

    v: int = Field(ge=1)
    type: str
    json_payload: dict[str, object] = Field(alias="json")
