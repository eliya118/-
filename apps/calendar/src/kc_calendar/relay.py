"""Publish outbox rows to Redis after the database commit that wrote them."""

import asyncio
import datetime as dt
import json
import logging

from sqlalchemy import delete, select

from kc_calendar.db.models import Event, Outbox
from kc_calendar.domain.timeutil import now_jerusalem

log = logging.getLogger("calendar.relay")
STREAM_KEY = "stream:calendar.events"


async def publish_pending(session_factory, redis) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(Outbox).where(Outbox.published_at.is_(None)).order_by(Outbox.created_at).limit(50)
            )
        ).all()
        pending = [(row.id, row.type, row.payload, row.attempts) for row in rows]
    if not pending:
        return
    published: list[tuple[object, int]] = []
    for row_id, event_type, payload, attempts in pending:
        await redis.xadd(
            STREAM_KEY,
            {"v": "1", "type": event_type, "json": json.dumps(payload)},
            maxlen=10000,
            approximate=True,
        )
        published.append((row_id, attempts + 1))
    async with session_factory() as session:
        rows = (await session.scalars(select(Outbox).where(Outbox.id.in_([row_id for row_id, _ in published])))).all()
        stamped = {row_id: attempts for row_id, attempts in published}
        now = now_jerusalem()
        for row in rows:
            if row.published_at is None:
                row.published_at = now
                row.attempts = stamped[row.id]
        await session.commit()


async def purge_deleted(session_factory) -> None:  # type: ignore[no-untyped-def]
    cutoff = now_jerusalem() - dt.timedelta(days=30)
    async with session_factory() as session:
        await session.execute(delete(Event).where(Event.deleted_at.is_not(None), Event.deleted_at < cutoff))
        await session.commit()


async def relay_loop(session_factory, redis, stop: asyncio.Event) -> None:  # type: ignore[no-untyped-def]
    while not stop.is_set():
        try:
            await publish_pending(session_factory, redis)
        except Exception:
            log.exception("outbox relay failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.0)
        except TimeoutError:
            continue


async def purge_loop(session_factory, stop: asyncio.Event) -> None:  # type: ignore[no-untyped-def]
    while not stop.is_set():
        try:
            await purge_deleted(session_factory)
        except Exception:
            log.exception("purge failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=3600)
        except TimeoutError:
            continue
