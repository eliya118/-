from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from notifier.schedule import (
    Decision,
    Status,
    apply_cancel,
    apply_upsert,
    decide_send,
    idempotency_key,
)

JERUSALEM = ZoneInfo("Asia/Jerusalem")
EVENT = UUID("00000000-0000-4000-8000-000000000010")
FAMILY = UUID("00000000-0000-4000-8000-000000000020")
NOW = datetime(2026, 1, 7, 9, tzinfo=JERUSALEM)


def _upsert(generation: int, remind_at: datetime | None, new: UUID):
    return dict(
        event_id=EVENT,
        family_id=FAMILY,
        generation=generation,
        channel="email",
        locale="he",
        title="dentist",
        starts_at=NOW + timedelta(hours=4),
        remind_at=remind_at,
        new_id=new,
    )


def test_idempotency_key_format_and_replay() -> None:
    assert idempotency_key(EVENT, 3, "email") == f"{EVENT}:3:email"
    first = apply_upsert([], **_upsert(1, NOW + timedelta(hours=3), UUID(int=1)))
    again = apply_upsert(first, **_upsert(1, NOW + timedelta(hours=3), UUID(int=2)))
    scheduled = [row for row in again if row.status == Status.scheduled]
    assert len(scheduled) == 1
    assert scheduled[0].id == UUID(int=1)
    assert scheduled[0].idempotency_key == idempotency_key(EVENT, 1, "email")


def test_newer_generation_cancels_the_old_row() -> None:
    first = apply_upsert([], **_upsert(1, NOW + timedelta(hours=3), UUID(int=1)))
    second = apply_upsert(first, **_upsert(2, NOW + timedelta(hours=2), UUID(int=2)))
    by_gen = {row.generation: row.status for row in second}
    assert by_gen[1] == Status.cancelled
    assert by_gen[2] == Status.scheduled


def test_null_remind_at_schedules_nothing() -> None:
    rows = apply_upsert([], **_upsert(1, None, UUID(int=1)))
    assert rows == []


def test_sent_and_live_lease_do_not_send_again() -> None:
    row = apply_upsert([], **_upsert(1, NOW + timedelta(hours=3), UUID(int=1)))[0]
    sent = row.__class__(**{**row.__dict__, "status": Status.sent})
    assert decide_send(sent, NOW) == Decision.noop
    leasing = row.__class__(
        **{**row.__dict__, "status": Status.sending, "lease_until": NOW + timedelta(minutes=1)}
    )
    assert decide_send(leasing, NOW) == Decision.retry
    expired = row.__class__(
        **{**leasing.__dict__, "lease_until": NOW - timedelta(seconds=1)}
    )
    assert decide_send(expired, NOW) == Decision.send
    cancelled = apply_cancel([row], EVENT)[0]
    assert cancelled.status == Status.cancelled
    assert decide_send(cancelled, NOW) == Decision.noop
