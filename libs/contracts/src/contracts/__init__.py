"""DTOs shared by calendar, intake, ideas, and notifier. No I/O."""

from contracts.drafts import Draft, IdeasResponse, ParseRequest, ParseResponse, Suggestion
from contracts.errors import ErrorBody, ErrorCode
from contracts.events import (
    ContactRemoved,
    ContactUpdated,
    EventCancelled,
    EventUpserted,
    StreamMessage,
)

__all__ = [
    "ContactRemoved",
    "ContactUpdated",
    "Draft",
    "ErrorBody",
    "ErrorCode",
    "EventCancelled",
    "EventUpserted",
    "IdeasResponse",
    "ParseRequest",
    "ParseResponse",
    "StreamMessage",
    "Suggestion",
]
