"""Reminder state machine. A recorded success is not sent again."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

LEASE = dt.timedelta(minutes=2)
BACKOFF_SECONDS = (60, 300, 900, 3600, 21600)
MAX_ATTEMPTS = 5


class Status(StrEnum):
    scheduled = "scheduled"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"


class Decision(StrEnum):
    send = "send"
    noop = "noop"
    retry = "retry"


def idempotency_key(event_id: UUID, generation: int, channel: str) -> str:
    return f"{event_id}:{generation}:{channel}"


def backoff_seconds(attempt: int) -> int:
    """attempt is 1-based. The fifth failure stops; this is the delay before the next try."""
    index = min(max(attempt, 1), len(BACKOFF_SECONDS)) - 1
    return BACKOFF_SECONDS[index]


@dataclass
class Reminder:
    id: UUID
    event_id: UUID
    family_id: UUID
    generation: int
    channel: str
    locale: str
    idempotency_key: str
    remind_at: dt.datetime | None
    starts_at: dt.datetime | None
    title: str
    status: str
    attempts: int = 0
    lease_until: dt.datetime | None = None
    sent_at: dt.datetime | None = None


def decide_send(row: Reminder, now: dt.datetime) -> Decision:
    if row.status in {Status.sent, Status.cancelled, Status.failed}:
        return Decision.noop
    if row.status == Status.sending:
        if row.lease_until is not None and row.lease_until > now:
            return Decision.retry
        return Decision.send
    if row.status == Status.scheduled:
        return Decision.send
    return Decision.noop


def apply_upsert(
    rows: list[Reminder],
    *,
    event_id: UUID,
    family_id: UUID,
    generation: int,
    channel: str,
    locale: str,
    title: str,
    starts_at: dt.datetime,
    remind_at: dt.datetime | None,
    new_id: UUID,
) -> list[Reminder]:
    """Cancel older generations. A null remind_at leaves nothing new scheduled."""
    updated: list[Reminder] = []
    for row in rows:
        if (
            row.event_id == event_id
            and row.generation < generation
            and row.status in {Status.scheduled, Status.sending}
        ):
            updated.append(replace(row, status=Status.cancelled))
        else:
            updated.append(row)
    if remind_at is None:
        return updated
    key = idempotency_key(event_id, generation, channel)
    if any(row.idempotency_key == key for row in updated):
        return updated
    updated.append(
        Reminder(
            id=new_id,
            event_id=event_id,
            family_id=family_id,
            generation=generation,
            channel=channel,
            locale=locale,
            idempotency_key=key,
            remind_at=remind_at,
            starts_at=starts_at,
            title=title,
            status=Status.scheduled,
        )
    )
    return updated


def apply_cancel(rows: list[Reminder], event_id: UUID) -> list[Reminder]:
    updated: list[Reminder] = []
    for row in rows:
        if row.event_id == event_id and row.status in {Status.scheduled, Status.sending}:
            updated.append(replace(row, status=Status.cancelled))
        else:
            updated.append(row)
    return updated
