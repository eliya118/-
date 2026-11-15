"""Stream consumer, reminder rows, and the send path."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from contracts.events import ContactRemoved, ContactUpdated, EventCancelled, EventUpserted, parse_event
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifier.channels.protocol import Channel, Delivery, PermanentError, TransientError
from notifier.db import Contact, ReminderRow
from notifier.ids import new_id
from notifier.schedule import (
    LEASE,
    MAX_ATTEMPTS,
    Decision,
    Reminder,
    Status,
    apply_cancel,
    apply_upsert,
    decide_send,
)

log = logging.getLogger("notifier.runtime")
JERUSALEM = ZoneInfo("Asia/Jerusalem")
STREAM_KEY = "stream:calendar.events"
GROUP = "notifier"
CONSUMER = "notifier-1"


def _now() -> dt.datetime:
    return dt.datetime.now(JERUSALEM)


def _to_domain(row: ReminderRow) -> Reminder:
    return Reminder(
        id=row.id,
        event_id=row.event_id,
        family_id=row.family_id,
        generation=row.generation,
        channel=row.channel,
        locale=row.locale,
        idempotency_key=row.idempotency_key,
        remind_at=row.remind_at,
        starts_at=row.starts_at,
        title=row.title,
        status=row.status,
        attempts=row.attempts,
        lease_until=row.lease_until,
        sent_at=row.sent_at,
    )


def _apply_domain(session: AsyncSession, before: list[ReminderRow], after: list[Reminder]) -> list[UUID]:
    by_id = {row.id: row for row in before}
    fresh: list[UUID] = []
    for item in after:
        existing = by_id.get(item.id)
        if existing is None:
            session.add(
                ReminderRow(
                    id=item.id,
                    event_id=item.event_id,
                    family_id=item.family_id,
                    generation=item.generation,
                    channel=item.channel,
                    locale=item.locale,
                    idempotency_key=item.idempotency_key,
                    remind_at=item.remind_at,
                    starts_at=item.starts_at,
                    title=item.title,
                    status=item.status,
                    attempts=item.attempts,
                    lease_until=item.lease_until,
                    sent_at=item.sent_at,
                )
            )
            if item.status == Status.scheduled:
                fresh.append(item.id)
        else:
            existing.status = item.status
            existing.title = item.title
            existing.remind_at = item.remind_at
            existing.starts_at = item.starts_at
    return fresh


async def handle_message(
    session: AsyncSession, event_type: str, payload: dict[str, Any], channels: set[str]
) -> list[UUID]:
    message = parse_event(event_type, payload)
    request_id = payload.get("request_id")
    if isinstance(message, ContactUpdated):
        if "email" not in channels:
            return []
        row = await session.get(Contact, (message.family_id, "email"))
        if row is None:
            session.add(
                Contact(
                    family_id=message.family_id,
                    channel="email",
                    destination=message.email,
                    locale=message.locale,
                )
            )
        else:
            row.destination = message.email
            row.locale = message.locale
        log.info("contact updated", extra={"family_id": str(message.family_id), "request_id": request_id})
        return []
    if isinstance(message, ContactRemoved):
        contacts = (await session.scalars(select(Contact).where(Contact.family_id == message.family_id))).all()
        for contact in contacts:
            await session.delete(contact)
        reminders = (
            await session.scalars(select(ReminderRow).where(ReminderRow.family_id == message.family_id))
        ).all()
        for row in reminders:
            if row.status in {Status.scheduled, Status.sending}:
                row.status = Status.cancelled
        log.info("contact removed", extra={"family_id": str(message.family_id), "request_id": request_id})
        return []
    if isinstance(message, EventCancelled):
        reminders = (await session.scalars(select(ReminderRow).where(ReminderRow.event_id == message.event_id))).all()
        _apply_domain(session, list(reminders), apply_cancel([_to_domain(row) for row in reminders], message.event_id))
        log.info(
            "event cancelled",
            extra={"event_id": str(message.event_id), "family_id": str(message.family_id), "request_id": request_id},
        )
        return []
    if isinstance(message, EventUpserted):
        fresh: list[UUID] = []
        for channel in sorted(channels):
            contact = await session.get(Contact, (message.family_id, channel))
            if contact is None:
                continue
            reminders = (
                await session.scalars(
                    select(ReminderRow).where(ReminderRow.event_id == message.event_id, ReminderRow.channel == channel)
                )
            ).all()
            updated = apply_upsert(
                [_to_domain(row) for row in reminders],
                event_id=message.event_id,
                family_id=message.family_id,
                generation=message.generation,
                channel=channel,
                locale=message.locale,
                title=message.title,
                starts_at=message.starts_at,
                remind_at=message.remind_at,
                new_id=new_id(),
            )
            fresh.extend(_apply_domain(session, list(reminders), updated))
        log.info(
            "event upserted",
            extra={"event_id": str(message.event_id), "family_id": str(message.family_id), "request_id": request_id},
        )
        return fresh
    return []


def _local_start(moment: dt.datetime | None) -> str:
    if moment is None:
        return ""
    return moment.astimezone(JERUSALEM).strftime("%Y-%m-%d %H:%M")


async def perform_send(
    factory: async_sessionmaker[AsyncSession],
    channels: dict[str, Channel],
    reminder_id: UUID,
) -> None:
    async with factory() as session:
        row = await session.get(ReminderRow, reminder_id, with_for_update=True)
        if row is None:
            return
        decision = decide_send(_to_domain(row), _now())
        if decision == Decision.noop:
            return
        if decision == Decision.retry:
            raise TransientError("lease still held")
        if row.attempts >= MAX_ATTEMPTS:
            row.status = Status.failed
            row.sent_at = _now()
            await session.commit()
            log.error("reminder failed", extra={"reminder_id": str(reminder_id)})
            return
        contact = await session.get(Contact, (row.family_id, row.channel))
        if contact is None:
            row.status = Status.failed
            row.sent_at = _now()
            await session.commit()
            log.error("reminder failed", extra={"reminder_id": str(reminder_id)})
            return
        row.status = Status.sending
        row.lease_until = _now() + LEASE
        row.attempts += 1
        attempt = row.attempts
        delivery = Delivery(
            idempotency_key=row.idempotency_key,
            locale=row.locale,
            title=row.title,
            local_start=_local_start(row.starts_at),
            destination=contact.destination,
        )
        channel = channels.get(row.channel)
        await session.commit()
    if channel is None:
        await _finish(factory, reminder_id, Status.failed)
        log.error("reminder failed", extra={"reminder_id": str(reminder_id)})
        return
    try:
        await asyncio.to_thread(channel.send, delivery)
    except PermanentError:
        await _finish(factory, reminder_id, Status.failed)
        log.error("reminder failed", extra={"reminder_id": str(reminder_id)})
        return
    except TransientError:
        if attempt >= MAX_ATTEMPTS:
            await _finish(factory, reminder_id, Status.failed)
            log.error("reminder failed", extra={"reminder_id": str(reminder_id)})
            return
        raise
    await _finish(factory, reminder_id, Status.sent)


async def _finish(factory: async_sessionmaker[AsyncSession], reminder_id: UUID, status: str) -> None:
    async with factory() as session:
        row = await session.get(ReminderRow, reminder_id)
        if row is None or row.status == Status.sent:
            return
        row.status = status
        row.sent_at = _now()
        row.lease_until = None
        await session.commit()


async def send_due(factory: async_sessionmaker[AsyncSession], channels: dict[str, Channel]) -> None:
    async with factory() as session:
        rows = (
            await session.scalars(
                select(ReminderRow).where(ReminderRow.status == Status.scheduled, ReminderRow.remind_at <= _now())
            )
        ).all()
        ids = [row.id for row in rows]
    for reminder_id in ids:
        try:
            await perform_send(factory, channels, reminder_id)
        except TransientError:
            log.warning("reminder retry", extra={"reminder_id": str(reminder_id)})


async def clear_old_titles(factory: async_sessionmaker[AsyncSession]) -> None:
    cutoff = _now() - dt.timedelta(days=7)
    async with factory() as session:
        await session.execute(
            update(ReminderRow)
            .where(
                ReminderRow.status.in_([Status.sent, Status.failed]),
                ReminderRow.sent_at.is_not(None),
                ReminderRow.sent_at < cutoff,
                ReminderRow.title != "",
            )
            .values(title="")
        )
        await session.commit()


async def consume_forever(  # type: ignore[no-untyped-def]
    redis,
    factory: async_sessionmaker[AsyncSession],
    channels: set[str],
    stop: asyncio.Event,
    pool=None,
) -> None:
    try:
        await redis.xgroup_create(STREAM_KEY, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            log.exception("consumer group create failed")
    while not stop.is_set():
        try:
            claimed = await redis.xautoclaim(STREAM_KEY, GROUP, CONSUMER, min_idle_time=60000, start_id="0-0", count=20)
            messages = claimed[1] if isinstance(claimed, (list, tuple)) and len(claimed) > 1 else []
            await _handle_batch(redis, factory, channels, messages, pool)
            batch = await redis.xreadgroup(GROUP, CONSUMER, {STREAM_KEY: ">"}, count=20, block=2000)
            if batch:
                for _stream, entries in batch:
                    await _handle_batch(redis, factory, channels, entries, pool)
        except Exception:
            log.exception("consumer loop failed")
            await asyncio.sleep(1)


async def _handle_batch(redis, factory, channels: set[str], entries, pool) -> None:  # type: ignore[no-untyped-def]
    for entry in entries or []:
        message_id, fields = entry
        try:
            event_type = fields["type"]
            payload = json.loads(fields["json"])
            async with factory() as session:
                fresh = await handle_message(session, event_type, payload, channels)
                await session.commit()
                scheduled = []
                if fresh:
                    rows = (await session.scalars(select(ReminderRow).where(ReminderRow.id.in_(fresh)))).all()
                    scheduled = [(row.id, row.remind_at) for row in rows if row.remind_at is not None]
            await redis.xack(STREAM_KEY, GROUP, message_id)
            if pool is not None:
                for reminder_id, remind_at in scheduled:
                    await pool.enqueue_job(
                        "send_reminder",
                        str(reminder_id),
                        _defer_until=remind_at,
                        _job_id=str(reminder_id),
                    )
        except Exception:
            log.exception("message failed", extra={"reminder_id": str(message_id)})
